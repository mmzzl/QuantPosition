from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Dict, Any, List
from datetime import datetime

from app.core.auth import AuthenticatedUser, get_current_user
from tasks.backtest_tasks import run_simple_backtest, run_rule_backtest
from database import get_db

router = APIRouter(prefix="/backtest", tags=["回测"])


@router.post("/simple")
async def backtest_simple_submit(
    strategy: str = Query("dual_ma", regex="^(dual_ma|news)$"),
    days_back: int = Query(180, ge=30, le=730),
    hold_days: str = Query("60"),
    use_rules: bool = Query(False),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        hold_list = [int(x) for x in hold_days.split(",") if x.strip().isdigit()]
        task = run_simple_backtest.delay(
            strategy=strategy,
            days_back=days_back,
            hold_days=hold_list or [60],
            use_rules=use_rules,
        )
        return {"task_id": task.id, "message": "回测任务已提交", "use_rules": use_rules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/with-rules")
async def backtest_rules_submit(
    days_back: int = Query(180, ge=30, le=730),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        task = run_rule_backtest.delay(days_back=days_back)
        return {"task_id": task.id, "message": "规则回测任务已提交"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/save")
async def save_backtest_result(
    data: Dict[str, Any] = Body(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    db = get_db()
    doc = {
        **data,
        "saved_at": datetime.now(),
    }
    db.backtest_results.replace_one({"_id": "latest"}, doc, upsert=True)
    return {"saved": True}


@router.get("/latest")
async def get_latest_backtest(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    db = get_db()
    doc = db.backtest_results.find_one({"_id": "latest"})
    if not doc:
        return {"exists": False}
    doc.pop("_id", None)
    doc.pop("saved_at", None)
    return doc


@router.get("/task/{task_id}")
async def get_backtest_task_status(
    task_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    from celery.result import AsyncResult

    task_result = AsyncResult(task_id)
    response = {"task_id": task_id, "status": task_result.status}

    if task_result.status == "SUCCESS":
        response["result"] = task_result.result
    elif task_result.status == "PROGRESS":
        response["progress"] = task_result.info
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.result)

    return response
