from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.core.auth import AuthenticatedUser, get_current_user
from services.sector_service import SectorService
from tasks.kline_tasks import update_kline_data

router = APIRouter(prefix="/sectors", tags=["板块热力图"])


@router.get("/heatmap")
async def get_sector_heatmap(
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取板块热力图数据"""
    try:
        result = SectorService.get_sector_heatmap(period, start_date, end_date)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热力图数据失败: {str(e)}"
        )


@router.get("/{sector_name}/stocks")
async def get_sector_stocks(
    sector_name: str,
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort_by: str = Query("change_pct", pattern="^(change_pct|volume|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取指定板块的股票列表"""
    try:
        result = SectorService.get_sector_stocks(
            sector_name, period, start_date, end_date, sort_by, sort_order, page, page_size
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取板块股票列表失败: {str(e)}"
        )


@router.post("/refresh-kline")
async def refresh_kline(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """触发 K 线数据更新（异步 Celery 任务）"""
    try:
        task = update_kline_data.delay()
        return {"task_id": task.id, "message": "K 线更新任务已提交"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.get("/kline/{code}")
async def get_kline_data(
    code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取股票K线数据，不传日期则自动取最近1年"""
    try:
        result = SectorService.get_kline_data(code, start_date, end_date)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取K线数据失败: {str(e)}"
        )
