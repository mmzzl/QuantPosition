from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
from app.core.auth import AuthenticatedUser, get_current_user
from database import get_db

router = APIRouter(prefix="/news", tags=["新闻"])


@router.get("")
async def get_news(
    period: str = Query("24h", pattern="^(24h|7d|30d|custom)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    db = get_db()

    date_filter = {}
    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="自定义时段需要提供 start_date 和 end_date")
        date_filter = {"showTime": {"$gte": start_date, "$lte": end_date + " 23:59:59"}}
    elif period == "7d":
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        date_filter = {"showTime": {"$gte": cutoff}}
    elif period == "30d":
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        date_filter = {"showTime": {"$gte": cutoff}}
    else:
        cutoff = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        date_filter = {"showTime": {"$gte": cutoff}}

    total = db.news.count_documents(date_filter)
    results = list(db.news.find(
        date_filter,
        {"_id": 0, "code": 1, "title": 1, "summary": 1, "showTime": 1, "stockList": 1}
    ).sort("showTime", -1).skip((page - 1) * page_size).limit(page_size))

    for r in results:
        if isinstance(r.get("showTime"), datetime):
            r["showTime"] = r["showTime"].strftime("%Y-%m-%d %H:%M")

    return {"news": results, "total": total, "page": page, "page_size": page_size}
