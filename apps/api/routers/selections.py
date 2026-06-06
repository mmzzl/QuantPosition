from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime, timedelta

from app.core.auth import AuthenticatedUser, get_current_user
from services.selection_service import StockSelectionService
from tasks.selection_tasks import run_dual_ma_selection

router = APIRouter(prefix="/selections", tags=["选股"])


@router.post("/dual-ma")
async def run_dual_ma_selection_api(
    short_period: int = Query(5, ge=1, le=20),
    long_period: int = Query(20, ge=5, le=60),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """运行双均线选股策略（异步）"""
    if short_period >= long_period:
        raise HTTPException(status_code=400, detail="short_period 必须小于 long_period")
    try:
        task = run_dual_ma_selection.delay(
            short_period=short_period,
            long_period=long_period
        )
        return {
            "task_id": task.id,
            "message": "选股任务已提交，请轮询任务状态"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交选股任务失败: {str(e)}"
        )


@router.get("/dual-ma/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """查询选股任务状态"""
    from celery.result import AsyncResult
    
    try:
        task_result = AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
        }
        
        if task_result.status == 'SUCCESS':
            response["result"] = task_result.result
        elif task_result.status == 'PROGRESS':
            response["progress"] = task_result.info
        elif task_result.status == 'FAILURE':
            response["error"] = str(task_result.result)
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务状态失败: {str(e)}"
        )


@router.get("/dual-ma")
async def get_dual_ma_results(
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    selection_start: Optional[str] = Query(None),
    selection_end: Optional[str] = Query(None),
    sort_by: str = Query("selection_date", pattern="^(selection_date|change_pct|current_price)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取双均线选股结果"""
    try:
        result = StockSelectionService.get_selection_results(
            period=period,
            start_date=start_date,
            end_date=end_date,
            selection_start=selection_start,
            selection_end=selection_end,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取选股结果失败: {str(e)}"
        )
