from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from database import get_db


class SectorService:
    """板块服务"""

    @staticmethod
    def get_sector_heatmap(period: str = "24h", start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """获取板块热力图数据"""
        db = get_db()
        kline_collection = db.stock_kline
        sector_collection = db.sector_stocks

        # 计算日期范围
        if start_date and end_date:
            start_str = start_date
            end_str = end_date
        else:
            end_dt = datetime.now()
            if period == "7d":
                start_dt = end_dt - timedelta(days=7)
            elif period == "30d":
                start_dt = end_dt - timedelta(days=30)
            else:  # 24h
                start_dt = end_dt - timedelta(days=1)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")

        # 获取所有板块及其股票
        all_sectors = list(sector_collection.find({}, {"sector_name": 1, "sector_code": 1, "stock_code": 1}))
        
        # 构建板块->股票代码映射
        sector_map = {}
        all_stock_codes = set()
        for item in all_sectors:
            sector_name = item["sector_name"]
            if sector_name not in sector_map:
                sector_map[sector_name] = {"sector_code": item.get("sector_code", ""), "stocks": []}
            pure_code = item["stock_code"].split(".")[-1] if "." in item["stock_code"] else item["stock_code"]
            sector_map[sector_name]["stocks"].append(pure_code)
            all_stock_codes.add(pure_code)

        # 批量查询所有股票的K线数据
        klines = list(kline_collection.find({
            "code": {"$in": list(all_stock_codes)},
            "frequency": 0,
            "date": {"$gte": start_str, "$lte": end_str + " 23:59"}
        }).sort("date", 1))

        # 按股票分组
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

        # 计算每个板块的涨跌幅
        heatmap_data = []
        for sector_name, sector_info in sector_map.items():
            changes = []
            total_volume = 0
            volume_count = 0
            stock_count = len(sector_info["stocks"])

            valid_codes = []
            for pure_code in sector_info["stocks"]:
                prices = stock_prices.get(pure_code)
                if prices:
                    first_close = prices["first"].get("close", 0)
                    last_close = prices["last"].get("close", 0)
                    if first_close > 0 and last_close > 0:
                        change_pct = ((last_close - first_close) / first_close) * 100
                        changes.append(change_pct)
                        valid_codes.append(pure_code)
                        total_volume += prices["last"].get("volume", 0)
                        volume_count += 1

            if changes:
                avg_change = sum(changes) / len(changes)
                heatmap_data.append({
                    "sector_name": sector_name,
                    "sector_code": sector_info["sector_code"],
                    "change_pct": round(avg_change, 2),
                    "stock_count": stock_count,
                    "avg_volume": round(total_volume / volume_count, 2) if volume_count > 0 else 0,
                    "start_price": round(sum(stock_prices[c]["first"]["close"] for c in valid_codes) / len(valid_codes), 2),
                    "end_price": round(sum(stock_prices[c]["last"]["close"] for c in valid_codes) / len(valid_codes), 2)
                })
            else:
                heatmap_data.append({
                    "sector_name": sector_name,
                    "sector_code": sector_info["sector_code"],
                    "change_pct": 0,
                    "stock_count": stock_count,
                    "avg_volume": 0,
                    "start_price": 0,
                    "end_price": 0
                })

        # 按涨跌幅排序
        heatmap_data.sort(key=lambda x: x["change_pct"], reverse=True)

        return {
            "sectors": heatmap_data,
            "period": period,
            "total_sectors": len(heatmap_data),
            "start_date": start_str,
            "end_date": end_str
        }

    @staticmethod
    def get_sector_stocks(sector_name: str, period: str = "24h", start_date: str = None, end_date: str = None, sort_by: str = "change_pct", sort_order: str = "desc", page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """获取指定板块的股票列表"""
        db = get_db()
        sector_collection = db.sector_stocks
        kline_collection = db.stock_kline

        # 获取板块内所有股票
        stocks = list(sector_collection.find({"sector_name": sector_name}))
        if not stocks:
            raise ValueError(f"板块不存在: {sector_name}")

        sector_code = stocks[0].get("sector_code", "")
        # 提取纯数字代码
        stock_codes = []
        code_map = {}  # pure_code -> original_code
        for s in stocks:
            code = s["stock_code"]
            pure_code = code.split(".")[-1] if "." in code else code
            stock_codes.append(pure_code)
            code_map[pure_code] = code

        # 计算日期范围
        if start_date and end_date:
            start_str = start_date
            end_str = end_date
        else:
            end_dt = datetime.now()
            if period == "7d":
                start_dt = end_dt - timedelta(days=7)
            elif period == "30d":
                start_dt = end_dt - timedelta(days=30)
            else:  # 24h
                start_dt = end_dt - timedelta(days=1)
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")

        # 查询时间段内K线数据
        klines = list(kline_collection.find({
            "code": {"$in": stock_codes},
            "frequency": 0,
            "date": {"$gte": start_str, "$lte": end_str + " 23:59"}
        }).sort("date", 1))

        # 按股票分组，找出期初和期末价格
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

        # 构建股票列表
        stock_list = []
        for stock in stocks:
            code = stock["stock_code"]
            pure_code = code.split(".")[-1] if "." in code else code
            prices = stock_prices.get(pure_code, {})
            first_kline = prices.get("first", {})
            last_kline = prices.get("last", {})

            current_price = last_kline.get("close", 0)
            open_price = first_kline.get("close", 0)
            change_pct = 0
            if open_price > 0 and current_price > 0:
                change_pct = ((current_price - open_price) / open_price) * 100

            stock_list.append({
                "code": code,
                "name": stock.get("stock_name", ""),
                "change_pct": round(change_pct, 2),
                "current_price": current_price,
                "open_price": open_price,
                "high": last_kline.get("high", 0),
                "low": last_kline.get("low", 0),
                "volume": last_kline.get("volume", 0),
                "amount": last_kline.get("amount", 0)
            })

        # 排序
        reverse = sort_order == "desc"
        if sort_by == "change_pct":
            stock_list.sort(key=lambda x: x["change_pct"], reverse=reverse)
        elif sort_by == "volume":
            stock_list.sort(key=lambda x: x["volume"], reverse=reverse)
        elif sort_by == "name":
            stock_list.sort(key=lambda x: x["name"], reverse=reverse)

        # 分页
        total = len(stock_list)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = stock_list[start:end]

        return {
            "sector_name": sector_name,
            "sector_code": sector_code,
            "stocks": paginated,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    @staticmethod
    def get_kline_data(code: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """获取股票K线数据"""
        db = get_db()
        kline_collection = db.stock_kline
        sector_collection = db.sector_stocks

        # 处理代码格式
        pure_code = code.split(".")[-1] if "." in code else code

        # 获取股票名称
        stock = sector_collection.find_one({"stock_code": {"$regex": f"{pure_code}$"}})
        stock_name = stock.get("stock_name", "") if stock else ""

        # 查询K线数据 (date格式: "2026-05-11 15:00")
        start_str = start_date
        end_str = end_date + " 23:59"

        klines = list(kline_collection.find({
            "code": pure_code,
            "frequency": 0,
            "date": {"$gte": start_str, "$lte": end_str}
        }).sort("date", 1))

        if not klines:
            raise ValueError(f"未找到股票K线数据: {code}")

        data = []
        for k in klines:
            date_str = k["date"]
            if isinstance(date_str, datetime):
                date_str = date_str.strftime("%Y-%m-%d")
            else:
                date_str = str(date_str).split(" ")[0]
            data.append({
                "date": date_str,
                "open": k.get("open", 0),
                "close": k.get("close", 0),
                "high": k.get("high", 0),
                "low": k.get("low", 0),
                "volume": k.get("volume", 0),
                "amount": k.get("amount", 0)
            })

        return {
            "code": code,
            "name": stock_name,
            "period": "daily",
            "data": data,
            "total": len(data)
        }
