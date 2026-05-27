from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any
from app.core.auth import AuthenticatedUser, get_current_user
from tasks.backtest_tasks import run_simple_backtest
from database import get_db

router = APIRouter(prefix="/backtest", tags=["回测"])


@router.post("/run")
async def submit_backtest(
    days_back: int = Query(180, ge=30, le=730),
    initial_cash: float = Query(100000, ge=10000),
    commission: float = Query(0.001, ge=0, le=0.05),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        task = run_simple_backtest.delay(
            days_back=days_back,
            initial_cash=initial_cash,
            commission=commission,
        )
        return {"task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_task_status(task_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    from celery.result import AsyncResult
    r = AsyncResult(task_id)
    resp = {"task_id": task_id, "status": r.status}
    if r.status == "SUCCESS":
        resp["result"] = r.result
    elif r.status == "PROGRESS":
        resp["progress"] = r.info
    elif r.status == "FAILURE":
        resp["error"] = str(r.result)
    return resp


@router.get("/latest")
async def get_latest(current_user: AuthenticatedUser = Depends(get_current_user)):
    db = get_db()
    doc = db.backtest_results.find_one({"_id": "latest"})
    if not doc:
        return {"exists": False}
    doc.pop("_id", None)
    doc.pop("saved_at", None)
    return doc
