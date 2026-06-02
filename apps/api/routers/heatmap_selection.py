from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.core.auth import AuthenticatedUser, get_current_user
from services.heatmap_selection_service import HeatmapSelectionService
from tasks.heatmap_selection_tasks import run_heatmap_selection

router = APIRouter(prefix="/heatmap-selection", tags=["热力图选股"])


@router.post("/run")
async def run_heatmap_selection_api(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """触发热力图选股任务（异步 Celery）"""
    try:
        task = run_heatmap_selection.delay()
        return {"task_id": task.id, "message": "热力图选股任务已提交"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交任务失败: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """查询热力图选股任务状态"""
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("")
async def get_heatmap_selection(
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    top_n: int = Query(5, ge=1, le=20),
    sort_by: str = Query("score", pattern="^(score|change_pct|current_price|volume|sector_name|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取热力图选股结果（从缓存读取）"""
    try:
        result = HeatmapSelectionService.get_heatmap_selection(
            period=period,
            start_date=start_date,
            end_date=end_date,
            top_n=top_n,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热力图选股结果失败: {str(e)}"
        )
