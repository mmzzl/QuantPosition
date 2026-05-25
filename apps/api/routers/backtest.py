from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List

from app.core.auth import AuthenticatedUser, get_current_user
from services.backtest_service import BacktestService

router = APIRouter(prefix="/backtest", tags=["回测"])


@router.get("/simple")
async def backtest_simple(
    strategy: str = Query("dual_ma", regex="^(dual_ma|news)$"),
    days_back: int = Query(180, ge=30, le=730),
    hold_days: str = Query("5,20,60"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        hold_list = [int(x) for x in hold_days.split(",") if x.strip().isdigit()]
        result = BacktestService.run_simple(
            strategy=strategy,
            days_back=days_back,
            hold_days=hold_list or [5, 20, 60],
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回测失败: {str(e)}",
        )


@router.get("/with-rules")
async def backtest_with_rules(
    days_back: int = Query(180, ge=30, le=730),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        result = BacktestService.run_with_rules(days_back=days_back)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"规则回测失败: {str(e)}",
        )
