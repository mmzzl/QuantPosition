import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List, Optional

from app.core.auth import AuthenticatedUser, get_current_user
from database import get_db
from services.sector_service import SectorService
from tasks.kline_tasks import update_kline_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sectors", tags=["板块热力图"])


@router.get("/heatmap")
async def get_sector_heatmap(
    period: str = Query("24h", pattern="^(24h|7d|30d|custom)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    if period == "custom" and (not start_date or not end_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period=custom 时必须提供 start_date 和 end_date",
        )
    try:
        result = SectorService.get_sector_heatmap(period, start_date, end_date)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"获取热力图失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取热力图数据失败: {str(e)}",
        )


@router.get("/{sector_name}/stocks")
async def get_sector_stocks(
    sector_name: str,
    period: str = Query("24h", pattern="^(24h|7d|30d|custom)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort_by: str = Query("change_pct", pattern="^(change_pct|volume|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    if period == "custom" and (not start_date or not end_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period=custom 时必须提供 start_date 和 end_date",
        )
    try:
        result = SectorService.get_sector_stocks(
            sector_name, period, start_date, end_date, sort_by, sort_order, page, page_size
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"获取板块股票列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取板块股票列表失败: {str(e)}",
        )


@router.post("/refresh-kline")
async def refresh_kline(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        task = update_kline_data.delay()
        return {"task_id": task.id, "message": "K 线更新任务已提交"}
    except Exception as e:
        logger.error(f"提交K线刷新任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.get("/_debug/mongo")
async def debug_mongo():
    """临时诊断接口：检查 MongoDB 中 stock_kline 数据"""
    db = get_db()
    sector_count = db.sector_stocks.count_documents({})
    kline_total = db.stock_kline.count_documents({})
    kline_freq9 = db.stock_kline.count_documents({"frequency": 9})
    freqs = db.stock_kline.distinct("frequency")

    latest_5 = list(db.stock_kline.find({"frequency": 9}).sort("date", -1).limit(5))
    latest_fmt = []
    for d in latest_5:
        latest_fmt.append({
            "code": d.get("code"),
            "date": str(d.get("date")),
            "close": d.get("close"),
            "frequency": d.get("frequency"),
        })

    start_str = "2026-08-03"
    end_str = "2026-08-04 23:59"
    matched = db.stock_kline.count_documents({
        "frequency": 9, "date": {"$gte": start_str, "$lte": end_str}
    })

    # Test the aggregate pipeline
    codes = list(db.stock_kline.distinct("code", {"frequency": 9}))
    pipeline_test = list(db.stock_kline.aggregate([
        {"$match": {"code": {"$in": codes[:5]}, "frequency": 9, "date": {"$gte": start_str, "$lte": end_str}}},
        {"$sort": {"code": 1, "date": 1}},
        {"$group": {"_id": "$code", "first_close": {"$first": "$close"}, "last_close": {"$last": "$close"}}}
    ]))

    return {
        "sector_stocks_count": sector_count,
        "stock_kline_total": kline_total,
        "stock_kline_freq9": kline_freq9,
        "frequencies": list(freqs),
        "latest_5_freq9": latest_fmt,
        "matched_24h_range": matched,
        "aggregate_pipeline_test_count": len(pipeline_test),
        "aggregate_sample": pipeline_test[:3] if pipeline_test else [],
        "unique_codes_freq9": len(codes),
    }


@router.get("/kline/{code}")
async def get_kline_data(
    code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        result = SectorService.get_kline_data(code, start_date, end_date)
        return result
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取K线数据失败: {str(e)}",
        )