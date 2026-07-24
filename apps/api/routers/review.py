from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.core.auth import AuthenticatedUser, get_current_user
from services.review_service import ReviewService
from database import get_db

router = APIRouter(prefix="/review", tags=["收盘复盘"])


@router.get("/latest")
def get_latest_review(current_user: AuthenticatedUser = Depends(get_current_user)):
    db = get_db()
    doc = db.review_reports.find_one(sort=[("date", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="暂无复盘报告")
    doc.pop("_id", None)
    return doc


@router.get("/list")
def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    db = get_db()
    total = db.review_reports.count_documents({})
    docs = list(
        db.review_reports.find({}, {"_id": 0})
        .sort("date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {"total": total, "items": docs}


@router.get("/{date}")
def get_review_by_date(
    date: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    db = get_db()
    doc = db.review_reports.find_one({"date": date}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{date} 无复盘报告")
    return doc
