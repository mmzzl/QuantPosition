from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from database import get_db


class HeatmapSelectionService:

    @staticmethod
    def get_heatmap_selection(
        period: str = "24h",
        start_date: str = None,
        end_date: str = None,
        top_n: int = 5,
        sort_by: str = "score",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        db = get_db()
        cache = db.heatmap_selection_cache

        if start_date and end_date:
            dt_filter = {
                "created_at": {
                    "$gte": datetime.strptime(start_date, "%Y-%m-%d"),
                    "$lte": datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                }
            }
        else:
            now = datetime.now()
            if period == "7d":
                cutoff = now - timedelta(days=7)
            elif period == "30d":
                cutoff = now - timedelta(days=30)
            else:
                cutoff = now - timedelta(days=1)
            dt_filter = {"created_at": {"$gte": cutoff}}

        # 用 MongoDB aggregation 计算每板块平均涨跌幅，只取 top-N
        pipeline = [
            {"$match": dt_filter},
            {"$group": {
                "_id": "$sector_name",
                "avg_change_pct": {"$avg": "$change_pct"},
                "stock_count": {"$sum": 1}
            }},
            {"$sort": {"avg_change_pct": -1}},
            {"$limit": top_n}
        ]
        sector_aggregates = list(cache.aggregate(pipeline))
        sectors = [{
            "sector_name": s["_id"],
            "avg_change_pct": round(s["avg_change_pct"], 2),
            "stock_count": s["stock_count"]
        } for s in sector_aggregates]

        top_sector_names = {s["sector_name"] for s in sectors}

        if not top_sector_names:
            return {
                "sectors": [],
                "stocks": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "strategy": "heatmap_selection",
                "filter_summary": {"total_raw": 0, "total_filtered": 0}
            }

        stock_query = {"sector_name": {"$in": list(top_sector_names)}}
        all_stocks = list(cache.find(stock_query))

        stock_list = []
        for s in all_stocks:
            sn = s.get("sector_name", "")

            score = 0
            flags = []
            pct = s.get("change_pct", 0)
            vol = s.get("volume", 0)
            price = s.get("current_price", 0)
            rank_pct = s.get("sector_rank_pct", 100)

            if rank_pct <= 20:
                score += 40
                flags.append("板块龙头")
            elif rank_pct <= 40:
                score += 25
                flags.append("板块前列")

            if vol > 100_000_000:
                score += 20
                flags.append("巨量活跃")
            elif vol > 10_000_000:
                score += 10
                flags.append("成交活跃")

            if price >= 20:
                score += 20
                flags.append("中高价")
            elif price >= 10:
                score += 10
                flags.append("中价")

            if pct > 10:
                score += 20
                flags.append("大涨")
            elif pct > 5:
                score += 10
                flags.append("强势")

            stock_list.append({
                "code": s.get("code", ""),
                "name": s.get("name", ""),
                "sector_name": sn,
                "current_price": price,
                "open_price": s.get("open_price", 0),
                "change_pct": pct,
                "volume": vol,
                "amount": s.get("amount", 0),
                "score": score,
                "heatmap_score": score,
                "grade": "S" if score >= 80 else "A" if score >= 60 else "B" if score >= 40 else "C",
                "flags": flags,
                "sector_rank": s.get("sector_rank", 0),
                "sector_rank_pct": rank_pct
            })

        sort_field_map = {
            "score": "score",
            "change_pct": "change_pct",
            "current_price": "current_price",
            "volume": "volume",
            "sector_name": "sector_name",
            "name": "name"
        }
        sf = sort_field_map.get(sort_by, "score")
        reverse = sort_order == "desc"
        stock_list.sort(key=lambda x: x[sf], reverse=reverse)

        total = len(stock_list)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = stock_list[start:end]

        return {
            "sectors": sectors[:top_n],
            "stocks": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "strategy": "heatmap_selection",
            "filter_summary": {
                "total_raw": len(all_stocks),
                "total_filtered": total
            }
        }
