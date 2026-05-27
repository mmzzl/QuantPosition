from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List

from app.core.auth import AuthenticatedUser, get_current_user
from tasks.backtest_tasks import run_simple_backtest
from services.backtest_engine import STRATEGY_MAP
from database import get_db

router = APIRouter(prefix="/backtest", tags=["回测"])


@router.get("/strategies")
async def get_strategies(current_user: AuthenticatedUser = Depends(get_current_user)):
    return {"strategies": list(STRATEGY_MAP.keys())}


@router.post("/simple")
async def backtest_simple_submit(
    strategy: str = Query("dual_ma"),
    days_back: int = Query(180, ge=30, le=730),
    hold_days: str = Query("60"),
    use_rules: bool = Query(False),
    initial_cash: float = Query(100000, ge=10000),
    commission: float = Query(0.001, ge=0, le=0.05),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        task = run_simple_backtest.delay(
            strategy=strategy,
            days_back=days_back,
            use_rules=use_rules,
            initial_cash=initial_cash,
            commission=commission,
        )
        return {"task_id": task.id, "message": f"回测任务已提交: {strategy}", "strategy": strategy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.get("/latest")
async def get_latest_backtest(current_user: AuthenticatedUser = Depends(get_current_user)):
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
