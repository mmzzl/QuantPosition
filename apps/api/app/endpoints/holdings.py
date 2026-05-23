from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List
from bson import ObjectId
from pydantic import BaseModel

from app.core.auth import AuthenticatedUser, get_current_user
from models.holding import HoldingCreate, HoldingUpdate, SellRequest, ExitRuleRequest, HoldingResponse
from services.holding_service import HoldingService
from services.transaction_service import TransactionService
from database import get_db
from models.user import User
from utils.stock_api import SinaStockAPI, get_stock_price


class PriceRequest(BaseModel):
    codes: List[str]

router = APIRouter(prefix="/holdings", tags=["持仓管理"])


@router.get("/{user_id}", response_model=Dict)
async def get_holdings(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取持仓列表"""
    # 普通用户只能查看自己的持仓
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该用户持仓"
        )

    return HoldingService.get_holdings(user_id, page, page_size)


@router.post("/prices")
async def get_stock_prices(
    request: PriceRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """批量获取股票实时价格"""
    prices = {}
    for code in request.codes:
        try:
            info = SinaStockAPI.get_stock_info(code)
            if info:
                prices[code] = {
                    "price": info.get("price"),
                    "name": info.get("name"),
                    "open": info.get("open"),
                    "high": info.get("high"),
                    "low": info.get("low"),
                    "volume": info.get("volume"),
                    "amount": info.get("amount")
                }
        except Exception:
            pass
    return {"prices": prices}


@router.post("/{user_id}", status_code=status.HTTP_201_CREATED)
async def buy_holding(
    user_id: str,
    holding_data: HoldingCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """买入/添加持仓"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作"
        )

    try:
        result = HoldingService.create_holding(user_id, holding_data)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{user_id}/{code}/sell")
async def sell_holding(
    user_id: str,
    code: str,
    sell_data: SellRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """卖出持仓"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作"
        )

    try:
        result = HoldingService.sell_holding(user_id, code, sell_data)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{user_id}/{code}")
async def delete_holding(
    user_id: str,
    code: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """删除持仓"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作"
        )

    success = HoldingService.delete_holding(user_id, code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="持仓不存在"
        )

    return {"message": "删除成功"}


@router.get("/{user_id}/history")
async def get_holding_history(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取持仓历史"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问"
        )

    return TransactionService.get_history(user_id, page, page_size)


@router.get("/{user_id}/exit-rule")
async def get_exit_rule(
    user_id: str,
    code: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取卖出规则"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问"
        )

    holding = HoldingService.get_holding(user_id, code)
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="持仓不存在"
        )

    return {"exit_rule": holding.get("exit_rule")}


@router.put("/{user_id}/{code}/exit-rule")
async def set_exit_rule(
    user_id: str,
    code: str,
    exit_rule: ExitRuleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """设置卖出规则"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作"
        )

    result = HoldingService.update_exit_rule(user_id, code, exit_rule)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="持仓不存在"
        )

    return result


# ===== 交易记录 =====

@router.get("/transactions/{user_id}")
async def get_transactions(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取交易记录"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问"
        )

    return TransactionService.get_transactions(user_id, page, page_size)


@router.delete("/transactions/{user_id}/{transaction_id}")
async def delete_transaction(
    user_id: str,
    transaction_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """删除交易记录"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作"
        )

    success = TransactionService.delete_transaction(user_id, transaction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="交易记录不存在"
        )

    return {"message": "删除成功"}


# ===== 盈亏 =====

@router.get("/pnl/{user_id}")
async def get_pnl(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取已实现盈亏"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问"
        )

    realized_pnl = TransactionService.get_realized_pnl(user_id)
    return {"realized_pnl": realized_pnl}


@router.get("/pnl/admin")
async def get_admin_pnl(current_user: AuthenticatedUser = Depends(get_current_user)):
    """管理员获取所有用户已实现盈亏"""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    return TransactionService.get_all_realized_pnl()


# ===== 组合汇总 =====

@router.get("/portfolio/{user_id}")
async def get_portfolio(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """获取组合汇总"""
    if current_user.user_id != user_id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问"
        )

    holdings_data = HoldingService.get_holdings(user_id, page=1, page_size=1000)
    
    # 为组合汇总获取实时价格
    for h in holdings_data["items"]:
        current_price = get_stock_price(h["code"])
        h["current_price"] = current_price
        h["market_value"] = current_price * h["quantity"] if current_price else 0
        h["unrealized_pnl"] = (current_price - h["average_cost"]) * h["quantity"] if current_price else 0

    holdings_count = len(holdings_data["items"])
    total_cost = sum(h["quantity"] * h["average_cost"] for h in holdings_data["items"])
    market_value = sum(h.get("market_value", 0) or 0 for h in holdings_data["items"])
    unrealized_pnl = sum(h.get("unrealized_pnl", 0) or 0 for h in holdings_data["items"])

    profit_rate = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0
    realized_pnl = TransactionService.get_realized_pnl(user_id)

    return {
        "holdings_count": holdings_count,
        "total_cost": round(total_cost, 2),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "profit_rate": round(profit_rate, 2),
        "realized_pnl": realized_pnl,
        "holdings": holdings_data["items"]
    }


# ===== 管理员接口 =====

@router.get("/admin")
async def get_admin_holdings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """管理员获取所有用户持仓"""
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    return HoldingService.get_all_holdings(page, page_size)


def _is_admin(user: AuthenticatedUser) -> bool:
    """检查是否为管理员"""
    # 需要根据实际角色系统判断，这里简化处理
    # 可以通过查询用户角色来判断
    db = get_db()
    users_collection = db.users

    try:
        user_doc = users_collection.find_one({"_id": ObjectId(user.user_id)})
        if user_doc:
            role = user_doc.get("role")
            return role == "admin"
    except Exception:
        pass

    return False