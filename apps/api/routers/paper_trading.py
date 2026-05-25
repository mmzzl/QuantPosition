from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from app.core.auth import AuthenticatedUser, get_current_user
from services.paper_trade_service import PaperTradingService

router = APIRouter(prefix="/paper-trading", tags=["模拟盘"])


@router.get("/positions")
async def get_paper_positions(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return PaperTradingService.get_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-buy")
async def sync_buy(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return PaperTradingService.sync_from_selections()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-sell")
async def sync_sell(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return PaperTradingService.sync_sell_rules()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_paper(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return PaperTradingService.clear_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
