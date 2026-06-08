from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any
from datetime import datetime
from app.core.auth import AuthenticatedUser, get_current_user
from tasks.backtest_tasks import run_simple_backtest
from database import get_db

router = APIRouter(prefix="/backtest", tags=["回测"])


@router.post("/run")
def submit_backtest(
    days_back: int = Query(360, ge=30, le=730),
    initial_cash: float = Query(100000, ge=10000),
    commission: float = Query(0.001, ge=0, le=0.05),
    max_stocks: int = Query(500, ge=0, le=5000),
    max_positions: int = Query(5, ge=1, le=20),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        task = run_simple_backtest.delay(
            days_back=days_back,
            initial_cash=initial_cash,
            commission=commission,
            max_stocks=max_stocks,
            max_positions=max_positions,
        )
        # 预先写入进度记录，用于检测 Celery 是否存活
        db = get_db()
        db.backtest_progress.update_one(
            {"_id": task.id},
            {"$set": {
                "status": "submitted", "submitted_at": datetime.now(),
                "current": 0, "total": 0, "detail": ""
            }},
            upsert=True,
        )
        return {"task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
def get_task_status(task_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    db = get_db()
    resp = {"task_id": task_id}

    # 读进度——这被 run_backtest 中的 _update_progress 持续写入
    prog = db.backtest_progress.find_one({"_id": task_id})
    if not prog:
        resp["status"] = "PENDING"
        resp["progress"] = {"current": 0, "total": 0, "status": "等待中...", "detail": ""}
        return resp

    prog_status = prog.get("status", "")
    submitted_at = prog.get("submitted_at")

    # --- 终态判定：失败 ---
    if prog_status in ("回测失败", "error"):
        resp["status"] = "FAILURE"
        resp["error"] = prog.get("detail", "回测执行失败")
        return resp

    # --- 终态判定：成功（兼容「回测完成」和「回测完成（无交易）」） ---
    if prog_status.startswith("回测完成"):
        # 结果优先从 progress 里的内嵌 result 读，兼容无 result backend
        inline_result = prog.get("result")
        if inline_result:
            resp["status"] = "SUCCESS"
            resp["result"] = inline_result
        else:
            from celery.result import AsyncResult
            r = AsyncResult(task_id)
            if r.status == "SUCCESS":
                resp["status"] = "SUCCESS"
                resp["result"] = r.result
            else:
                latest = db.backtest_results.find_one({"_id": "latest"})
                if latest:
                    latest.pop("_id", None)
                    latest.pop("saved_at", None)
                    resp["status"] = "SUCCESS"
                    resp["result"] = latest
                else:
                    resp["status"] = "SUCCESS"
                    resp["result"] = {
                        "trades": 0, "portfolio_return": 0,
                        "processed": prog.get("total", 0), "skipped": 0,
                    }
        return resp

    # --- 任务还在运行：检测 Celery 是否已死 ---
    if submitted_at and prog_status in ("submitted", "初始化...", "等待中...", ""):
        from celery.result import AsyncResult
        r = AsyncResult(task_id)
        if r.status == "PENDING":
            elapsed = (datetime.now() - submitted_at).total_seconds()
            if elapsed > 30:
                resp["status"] = "FAILURE"
                resp["error"] = "Celery 工作进程未运行，请检查 celery worker 是否已启动"
                return resp

    resp["status"] = "RUNNING"
    resp["progress"] = {
        "current": prog.get("current", 0),
        "total": prog.get("total", 0),
        "status": prog.get("status", ""),
        "detail": prog.get("detail", ""),
    }
    return resp


@router.get("/latest")
def get_latest(current_user: AuthenticatedUser = Depends(get_current_user)):
    db = get_db()
    doc = db.backtest_results.find_one({"_id": "latest"})
    if not doc:
        return {"exists": False}
    doc.pop("_id", None)
    doc.pop("saved_at", None)
    return doc
