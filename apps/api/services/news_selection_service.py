from datetime import datetime, timedelta
from typing import Dict, Any
from database import get_db


class NewsSelectionService:

    @staticmethod
    def get_news_stocks(
        period: str = "24h",
        sort_by: str = "expected_return",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        db = get_db()

        now = datetime.now()
        if period == "7d":
            cutoff = now - timedelta(days=7)
        elif period == "30d":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=1)

        query = {"created_at": {"$gte": cutoff}}
        total = db.news_selection_cache.count_documents(query)

        sort_dir = -1 if sort_order == "desc" else 1
        sort_field = sort_by if sort_by in ("expected_return", "current_price", "risk") else "expected_return"

        cursor = db.news_selection_cache.find(query).sort([(sort_field, sort_dir), ("_id", -1)])

        results = list(cursor.skip((page - 1) * page_size).limit(page_size))

        stocks = []
        for r in results:
            stocks.append({
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "bk_code": r.get("bk_code", ""),
                "bk_name": r.get("bk_name", ""),
                "news_titles": r.get("news_titles", []),
                "news_times": r.get("news_times", []),
                "current_price": r.get("current_price", 0),
                "target_price": r.get("target_price", 0),
                "stop_loss": r.get("stop_loss", 0),
                "expected_return": r.get("expected_return", 0),
                "risk": r.get("risk", 0),
                "ma_signal": r.get("ma_signal"),
            })

        return {"stocks": stocks, "total": total, "page": page, "page_size": page_size}
