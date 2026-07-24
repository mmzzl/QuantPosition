import copy
from datetime import datetime, timedelta
from typing import Dict, Any

from celery_config import celery_app
from database import get_db


def _normalize_code(code: str) -> str:
    """统一股票代码格式：去掉 .SZ/.SH 后缀"""
    return code.split(".")[0].strip()


@celery_app.task(bind=True, name="tasks.heatmap_selection.run_heatmap_selection")
def run_heatmap_selection(self) -> Dict[str, Any]:
    try:
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 0, 'status': '开始扫描板块...'})

        db = get_db()
        kline_collection = db.stock_kline
        bk_collection = db.bk_stocks
        cache_collection = db.heatmap_selection_cache

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=60)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        all_bk = list(bk_collection.find({}, {"bk_name": 1, "bk_code": 1, "stock_code": 1, "stock_name": 1}))

        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': len(all_bk), 'status': f'共{len(all_bk)}条板块映射，开始处理...'
        })

        sector_map = {}
        stock_to_sector = {}
        for item in all_bk:
            sector_name = item["bk_name"]
            if sector_name not in sector_map:
                sector_map[sector_name] = {"sector_code": item.get("bk_code", ""), "stocks": []}
            pure_code = _normalize_code(item["stock_code"])
            sector_map[sector_name]["stocks"].append(pure_code)
            if pure_code not in stock_to_sector:
                stock_to_sector[pure_code] = {
                    "sector_name": sector_name,
                    "stock_name": item.get("stock_name", "")
                }

        all_stock_codes = list(stock_to_sector.keys())

        klines = list(kline_collection.find({
            "code": {"$in": all_stock_codes},
            "frequency": 9,
            "date": {"$gte": start_str, "$lte": end_str + " 23:59"}
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

        sector_performance = []
        for sector_name, sector_info in sector_map.items():
            changes = []
            total_volume = 0
            v_count = 0
            for pure_code in sector_info["stocks"]:
                prices = stock_prices.get(pure_code)
                if prices:
                    fc = prices["first"].get("close", 0)
                    lc = prices["last"].get("close", 0)
                    if fc > 0 and lc > 0:
                        changes.append(((lc - fc) / fc) * 100)
                        total_volume += prices["last"].get("volume", 0)
                        v_count += 1
            if changes:
                avg_change = sum(changes) / len(changes)
            else:
                avg_change = 0
            sector_performance.append({
                "sector_name": sector_name,
                "sector_code": sector_info["sector_code"],
                "avg_change_pct": round(avg_change, 2),
                "stock_count": len(sector_info["stocks"]),
                "avg_volume": round(total_volume / v_count, 2) if v_count > 0 else 0
            })

        sector_performance.sort(key=lambda x: x["avg_change_pct"], reverse=True)
        top_sector_count = 10
        top_sectors = sector_performance[:top_sector_count]
        top_sector_names = {s["sector_name"] for s in top_sectors}

        self.update_state(state='PROGRESS', meta={
            'current': len(sector_performance), 'total': len(sector_performance),
            'status': f'板块计算完成，扫描Top{top_sector_count}板块个股...'
        })

        all_stocks = []
        for sector_name, sector_info in sector_map.items():
            if sector_name not in top_sector_names:
                continue
            raw = []
            for pure_code in sector_info["stocks"]:
                prices = stock_prices.get(pure_code)
                if not prices:
                    continue
                fc = prices["first"].get("close", 0)
                lc = prices["last"].get("close", 0)
                if fc <= 0 or lc <= 0:
                    continue
                change_pct = ((lc - fc) / fc) * 100
                name = stock_to_sector[pure_code]["stock_name"]
                if name.startswith("ST"):
                    continue
                raw.append({
                    "code": pure_code,
                    "name": name,
                    "sector_name": sector_name,
                    "current_price": lc,
                    "open_price": fc,
                    "change_pct": round(change_pct, 2),
                    "volume": prices["last"].get("volume", 0),
                    "amount": prices["last"].get("amount", 0),
                    "created_at": datetime.now()
                })
            raw.sort(key=lambda x: x["change_pct"], reverse=True)
            for rank, stock in enumerate(raw):
                stock["sector_rank"] = rank + 1
                stock["sector_rank_pct"] = round((rank + 1) / len(raw) * 100, 1) if raw else 100
            all_stocks.extend(raw)

        batch_id = int(datetime.now().timestamp() * 1000)
        for s in all_stocks:
            s["batch_id"] = batch_id
        if all_stocks:
            cache_collection.insert_many(copy.deepcopy(all_stocks))
            cache_collection.delete_many({"batch_id": {"$ne": batch_id}})

        filtered = _filter_stocks(all_stocks)

        self.update_state(state='PROGRESS', meta={
            'current': len(all_stocks), 'total': len(all_stocks),
            'status': f'热力图选股完成，原始{len(all_stocks)}只，筛选后{len(filtered)}只'
        })

        return {
            "sectors": top_sectors,
            "total_stocks_raw": len(all_stocks),
            "total_stocks": len(filtered),
            "strategy": "heatmap_selection",
            "message": f"选股完成，{len(top_sectors)}个强势板块共{len(all_stocks)}只，过滤后{len(filtered)}只可关注"
        }

    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'热力图选股失败: {str(e)}'})
        raise


def _filter_stocks(stocks):
    """基础过滤：板块排名前40%、成交量>0、股价>=5、涨幅>0"""
    result = []
    for s in stocks:
        if s.get("sector_rank_pct", 100) > 40:
            continue
        if s.get("volume", 0) <= 0:
            continue
        if s.get("current_price", 0) <= 5:
            continue
        if s.get("change_pct", 0) <= 0:
            continue
        result.append(s)
    return result
