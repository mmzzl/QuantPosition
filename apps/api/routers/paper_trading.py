import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import AuthenticatedUser, get_current_user
from services.paper_trade_service import PaperTradingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/paper-trading", tags=["模拟盘"])


@router.get("/positions")
def get_paper_positions(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return PaperTradingService.get_positions()
    except Exception as e:
        logger.error("Failed to get paper positions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-buy")
def sync_buy(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return PaperTradingService.sync_buy()
    except Exception as e:
        logger.error("Failed to sync buy: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-sell")
def sync_sell(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        PaperTradingService.sync_sell()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Failed to sync sell: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
def clear_paper(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        PaperTradingService.clear()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Failed to clear paper trading: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
