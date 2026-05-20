from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.core.auth import AuthenticatedUser, get_current_user
from services.news_selection_service import NewsSelectionService
from tasks.news_selection_tasks import run_news_selection

router = APIRouter(prefix="/news-selection", tags=["新闻选股"])


@router.post("/run")
async def run_news_selection_api(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """触发新闻选股任务（异步）"""
    try:
        task = run_news_selection.delay()
        return {"task_id": task.id, "message": "新闻选股任务已提交"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """查询任务状态"""
    from celery.result import AsyncResult
    try:
        task_result = AsyncResult(task_id)
        response = {"task_id": task_id, "status": task_result.status}
        if task_result.status == 'SUCCESS':
            response["result"] = task_result.result
        elif task_result.status == 'PROGRESS':
            response["progress"] = task_result.info
        elif task_result.status == 'FAILURE':
            response["error"] = str(task_result.result)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks")
async def get_news_stocks(
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    sort_by: str = Query("expected_return", pattern="^(expected_return|current_price|risk)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    try:
        result = NewsSelectionService.get_news_stocks(
            period=period, sort_by=sort_by, sort_order=sort_order,
            page=page, page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
