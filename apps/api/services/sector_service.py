import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import get_db

logger = logging.getLogger(__name__)


class SectorService:
    """板块服务 – 板块热力图、板块股票列表、K线查询、K线刷新"""

    SECTOR_COLLECTION = "sector_stocks"
    KLINE_COLLECTION = "stock_kline"

    @staticmethod
    def _resolve_date_range(period: str, start_date: Optional[str], end_date: Optional[str]):
        if period == "custom":
            if not start_date or not end_date:
                raise ValueError("period=custom 时必须提供 start_date 和 end_date")
            return start_date, end_date + " 23:59"

        if start_date and end_date:
            return start_date, end_date + " 23:59"

        end_dt = datetime.now()
        if period == "7d":
            start_dt = end_dt - timedelta(days=7)
        elif period == "30d":
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = end_dt - timedelta(days=1)

        return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d") + " 23:59"

    @staticmethod
    def get_sector_heatmap(
        period: str = "24h",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取板块热力图数据 – MongoDB aggregate pipeline 按板块+时间范围计算等权涨跌幅"""
        db = get_db()
        sector_collection = db[SectorService.SECTOR_COLLECTION]
        kline_collection = db[SectorService.KLINE_COLLECTION]

        start_str, end_str = SectorService._resolve_date_range(period, start_date, end_date)

        sectors = list(sector_collection.find({}, {"sector_name": 1, "sector_code": 1, "_id": 0}))
        if not sectors:
            return {"sectors": [], "period": period, "total_sectors": 0,
                    "start_date": start_str.split(" ")[0], "end_date": end_str.split(" ")[0]}

        seen = {}
        for s in sectors:
            if s["sector_name"] not in seen:
                seen[s["sector_name"]] = {"sector_name": s["sector_name"],
                                          "sector_code": s.get("sector_code", ""), "stocks": []}

        sector_stocks = list(sector_collection.find(
            {"sector_name": {"$in": list(seen.keys())}},
            {"sector_name": 1, "stock_code": 1, "stock_name": 1, "_id": 0}
        ))
        for ss in sector_stocks:
            raw_code = ss["stock_code"]
            # stock_code format: "sh.600000" or "000001" → extract numeric part
            if "." in raw_code:
                parts = raw_code.split(".")
                # "sh.600000" → "600000" (take last part), "600000.SH" → "600000"
                pure_code = parts[1] if len(parts[1]) >= 6 else parts[0]
            else:
                pure_code = raw_code
            if ss["sector_name"] in seen:
                seen[ss["sector_name"]]["stocks"].append(pure_code)

        all_codes = set()
        for info in seen.values():
            all_codes.update(info["stocks"])
        if not all_codes:
            heatmap_data = [{"sector_name": s["sector_name"],
                             "sector_code": s["sector_code"],
                             "change_pct": 0, "stock_count": len(s["stocks"]),
                             "volume": 0} for s in seen.values()]
            heatmap_data.sort(key=lambda x: x["change_pct"], reverse=True)
            return {"sectors": heatmap_data, "period": period,
                    "total_sectors": len(heatmap_data),
                    "start_date": start_str.split(" ")[0],
                    "end_date": end_str.split(" ")[0]}

        base_date = start_str.split(" ")[0]
        end_date_only = end_str.split(" ")[0]

        pipeline = [
            {"$match": {
                "code": {"$in": list(all_codes)},
                "frequency": 9,
                "date": {"$gte": start_str, "$lte": end_str}
            }},
            {"$sort": {"code": 1, "date": 1}},
            {"$group": {
                "_id": "$code",
                "first_close": {"$first": "$close"},
                "first_date": {"$first": "$date"},
                "last_close": {"$last": "$close"},
                "last_date": {"$last": "$date"},
                "last_volume": {"$last": "$volume"}
            }}
        ]
        agg_result = list(kline_collection.aggregate(pipeline))

        stock_prices = {}
        for doc in agg_result:
            code = doc["_id"]
            fc = doc.get("first_close", 0)
            lc = doc.get("last_close", 0)
            lv = doc.get("last_volume", 0)
            if fc > 0 and lc > 0:
                stock_prices[code] = {
                    "change_pct": ((lc - fc) / fc) * 100,
                    "volume": lv,
                    "first_close": fc,
                    "last_close": lc,
                }

        heatmap_data = []
        for sector_name, sector_info in seen.items():
            changes = []
            volumes = []
            for pure_code in sector_info["stocks"]:
                sp = stock_prices.get(pure_code)
                if sp:
                    changes.append(sp["change_pct"])
                    volumes.append(sp["volume"])

            stock_count = len(sector_info["stocks"])
            if changes:
                heatmap_data.append({
                    "sector_name": sector_name,
                    "sector_code": sector_info["sector_code"],
                    "change_pct": round(sum(changes) / len(changes), 2),
                    "stock_count": stock_count,
                    "volume": round(sum(volumes) / len(volumes), 2),
                })
            else:
                heatmap_data.append({
                    "sector_name": sector_name,
                    "sector_code": sector_info["sector_code"],
                    "change_pct": 0,
                    "stock_count": stock_count,
                    "volume": 0,
                })

        heatmap_data.sort(key=lambda x: x["change_pct"], reverse=True)
        return {
            "sectors": heatmap_data,
            "period": period,
            "total_sectors": len(heatmap_data),
            "start_date": base_date,
            "end_date": end_date_only,
        }

    @staticmethod
    def get_sector_stocks(
        sector_name: str,
        period: str = "24h",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "change_pct",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """获取指定板块的股票列表 — 不存在的板块返回空列表而非404"""
        db = get_db()
        sector_collection = db[SectorService.SECTOR_COLLECTION]

        stocks_in_sector = list(sector_collection.find(
            {"sector_name": sector_name},
            {"sector_code": 1, "stock_code": 1, "stock_name": 1, "_id": 0}
        ))
        if not stocks_in_sector:
            return {
                "sector_name": sector_name, "sector_code": "",
                "stocks": [], "total": 0, "page": page, "page_size": page_size,
            }

        sector_code = stocks_in_sector[0].get("sector_code", "")

        start_str, end_str = SectorService._resolve_date_range(period, start_date, end_date)
        kline_collection = db[SectorService.KLINE_COLLECTION]

        pure_codes = []
        code_map = {}
        for s in stocks_in_sector:
            raw_code = s["stock_code"]
            # stock_code format: "sh.600000" → extract numeric part
            if "." in raw_code:
                parts = raw_code.split(".")
                pure_code = parts[1] if len(parts[1]) >= 6 else parts[0]
            else:
                pure_code = raw_code
            pure_codes.append(pure_code)
            code_map[pure_code] = raw_code

        klines = list(kline_collection.find({
            "code": {"$in": pure_codes},
            "frequency": 9,
            "date": {"$gte": start_str, "$lte": end_str},
        }).sort("date", 1))

        stock_prices = {}
        for k in klines:
            code = k["code"]
            if code not in stock_prices:
                stock_prices[code] = {"first": k, "last": k}
            else:
                if k["date"] < stock_prices[code]["first"]["date"]:
                    stock_prices[code]["first"] = k
                if k["date"] > stock_prices[code]["last"]["date"]:
                    stock_prices[code]["last"] = k

        stock_list = []
        for s in stocks_in_sector:
            raw_code = s["stock_code"]
            # stock_code format: "sh.600000" → extract numeric part
            if "." in raw_code:
                parts = raw_code.split(".")
                pure_code = parts[1] if len(parts[1]) >= 6 else parts[0]
            else:
                pure_code = raw_code
            prices = stock_prices.get(pure_code, {})
            first_kline = prices.get("first", {})
            last_kline = prices.get("last", {})

            current_price = last_kline.get("close", 0)
            first_price = first_kline.get("close", 0)
            change_pct = 0
            if first_price > 0 and current_price > 0:
                change_pct = ((current_price - first_price) / first_price) * 100

            stock_list.append({
                "code": pure_code,
                "name": s.get("stock_name", ""),
                "change_pct": round(change_pct, 2),
                "current_price": current_price,
                "first_price": first_price,
                "high": last_kline.get("high", 0),
                "low": last_kline.get("low", 0),
                "volume": last_kline.get("volume", 0),
                "amount": last_kline.get("amount", 0),
            })

        reverse = sort_order == "desc"
        key_map = {"change_pct": "change_pct", "volume": "volume", "name": "name"}
        key_field = key_map.get(sort_by, "change_pct")
        if key_field == "name":
            stock_list.sort(key=lambda x: x["name"], reverse=reverse)
        else:
            stock_list.sort(key=lambda x: float(x.get(key_field, 0)), reverse=reverse)

        total = len(stock_list)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = stock_list[start_idx:end_idx]

        return {
            "sector_name": sector_name,
            "sector_code": sector_code,
            "stocks": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def get_kline_data(
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取股票K线数据 — 数据不存在返回空列表而非raise"""
        db = get_db()
        kline_collection = db[SectorService.KLINE_COLLECTION]
        sector_collection = db[SectorService.SECTOR_COLLECTION]

        # 处理代码格式: "sh.600000" → "600000"
        if "." in code:
            parts = code.split(".")
            pure_code = parts[1] if len(parts[1]) >= 6 else parts[0]
        else:
            pure_code = code

        # 获取股票名称
        stock = sector_collection.find_one({"stock_code": {"$regex": f"{pure_code}$"}})
        stock_name = stock.get("stock_name", "") if stock else ""

        # 日期范围
        if start_date and end_date:
            start_str = start_date
            end_str = end_date + " 23:59"
        else:
            latest = kline_collection.find_one(
                {"code": pure_code, "frequency": 9},
                sort=[("date", -1)],
            )
            if latest:
                raw = latest["date"]
                if isinstance(raw, datetime):
                    end_dt = raw
                else:
                    end_dt = datetime.strptime(str(raw).split(" ")[0], "%Y-%m-%d")
            else:
                end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=365)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d") + " 23:59"

        klines = list(kline_collection.find({
            "code": pure_code,
            "frequency": 9,
            "date": {"$gte": start_str, "$lte": end_str},
        }).sort("date", 1))

        data = []
        for k in klines:
            date_val = k["date"]
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val).split(" ")[0]
            data.append({
                "date": date_str,
                "open": k.get("open", 0),
                "close": k.get("close", 0),
                "high": k.get("high", 0),
                "low": k.get("low", 0),
                "volume": k.get("volume", 0),
                "amount": k.get("amount", 0),
            })

        return {
            "code": code,
            "name": stock_name,
            "period": "daily",
            "data": data,
            "total": len(data),
        }