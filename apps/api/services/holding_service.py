from bson import ObjectId
from datetime import datetime
from typing import Optional, List, Dict, Any
from database import get_db
from models.holding import HoldingCreate, HoldingUpdate, SellRequest, ExitRuleRequest
from utils.stock_api import get_stock_price, get_stock_name
from config.config import settings


def _is_shanghai(code: str) -> bool:
    return code.startswith("60") or code.startswith("688")


def calc_buy_fees(price: float, quantity: int, code: str) -> Dict[str, float]:
    amount = price * quantity
    commission = max(amount * settings.commission_rate, settings.min_commission)
    transfer_fee = amount * settings.transfer_rate if _is_shanghai(code) else 0
    return {"commission": round(commission, 2), "transfer_fee": round(transfer_fee, 2), "total": round(commission + transfer_fee, 2)}


def calc_sell_fees(price: float, quantity: int, code: str) -> Dict[str, float]:
    amount = price * quantity
    commission = max(amount * settings.commission_rate, settings.min_commission)
    transfer_fee = amount * settings.transfer_rate if _is_shanghai(code) else 0
    stamp_duty = amount * settings.stamp_duty_rate
    return {"commission": round(commission, 2), "transfer_fee": round(transfer_fee, 2), "stamp_duty": round(stamp_duty, 2), "total": round(commission + transfer_fee + stamp_duty, 2)}


class HoldingService:
    """持仓服务"""

    @staticmethod
    def create_holding(user_id: str, holding_data: HoldingCreate) -> Dict[str, Any]:
        """买入持仓，包含买入费用（佣金+过户费）"""
        db = get_db()
        holdings_collection = db.holdings

        buy_amount = holding_data.quantity * holding_data.average_cost
        fees = calc_buy_fees(holding_data.average_cost, holding_data.quantity, holding_data.code)
        buy_total = buy_amount + fees["total"]

        name = holding_data.name or get_stock_name(holding_data.code)

        existing = holdings_collection.find_one({
            "user_id": user_id,
            "code": holding_data.code
        })

        if existing:
            old_total_cost = existing.get("total_cost", existing["quantity"] * existing["average_cost"])
            new_quantity = existing["quantity"] + holding_data.quantity
            new_total_cost = round(old_total_cost + buy_total, 2)
            new_avg_cost = round(new_total_cost / new_quantity, 4)

            holdings_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "average_cost": new_avg_cost,
                        "total_cost": new_total_cost,
                        "updated_at": datetime.now()
                    }
                }
            )

            holding_id = str(existing["_id"])
            ret_quantity = new_quantity
            ret_avg_cost = round(new_total_cost / new_quantity, 2)
        else:
            now = datetime.now()
            new_total_cost = round(buy_total, 2)
            new_quantity = holding_data.quantity
            new_avg_cost = round(buy_total / holding_data.quantity, 4)

            result = holdings_collection.insert_one({
                "user_id": user_id,
                "code": holding_data.code,
                "name": name,
                "quantity": new_quantity,
                "average_cost": new_avg_cost,
                "total_cost": new_total_cost,
                "highest_price": holding_data.average_cost,
                "exit_rule": None,
                "tier_triggered": [False, False, False, False],
                "created_at": now,
                "updated_at": now
            })

            holding_id = str(result.inserted_id)
            ret_quantity = new_quantity
            ret_avg_cost = round(buy_total / holding_data.quantity, 2)

        # 记录买入交易（含费用）
        db.transactions.insert_one({
            "user_id": user_id,
            "code": holding_data.code,
            "type": "buy",
            "quantity": holding_data.quantity,
            "price": holding_data.average_cost,
            "total": buy_amount,
            "fees": fees["total"],
            "created_at": datetime.now()
        })

        return {
            "id": holding_id,
            "user_id": user_id,
            "code": holding_data.code,
            "name": name,
            "quantity": ret_quantity,
            "average_cost": ret_avg_cost
        }

    @staticmethod
    def sell_holding(user_id: str, code: str, sell_data: SellRequest) -> Dict[str, Any]:
        """卖出持仓，摊薄成本，记录已实现盈亏"""
        db = get_db()
        holdings_collection = db.holdings

        holding = holdings_collection.find_one({
            "user_id": user_id,
            "code": code
        })

        if not holding:
            raise ValueError("持仓不存在")

        if holding["quantity"] < sell_data.quantity:
            raise ValueError(f"持仓数量不足，当前持有 {holding['quantity']} 股")

        sell_amount = sell_data.quantity * sell_data.price
        fees = calc_sell_fees(sell_data.price, sell_data.quantity, code)
        sell_net = sell_amount - fees["total"]

        old_total_cost = holding.get("total_cost", holding["quantity"] * holding["average_cost"])
        old_avg_cost = holding["average_cost"]
        cost_of_sold = sell_data.quantity * old_avg_cost
        realized_pnl = round(sell_net - cost_of_sold, 2)

        new_quantity = holding["quantity"] - sell_data.quantity
        now = datetime.now()

        # 记录卖出交易（含费用、已实现盈亏）
        db.transactions.insert_one({
            "user_id": user_id,
            "code": code,
            "type": "sell",
            "quantity": sell_data.quantity,
            "price": sell_data.price,
            "total": sell_amount,
            "fees": fees["total"],
            "realized_pnl": realized_pnl,
            "created_at": now
        })

        if new_quantity == 0:
            holdings_collection.delete_one({"_id": holding["_id"]})
        else:
            # 摊薄成本：剩余总成本 = 原总成本 - 卖出对应成本
            remaining_cost = old_total_cost - cost_of_sold
            new_avg_cost = remaining_cost / new_quantity if remaining_cost > 0 else 0

            holdings_collection.update_one(
                {"_id": holding["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "average_cost": round(new_avg_cost, 4),
                        "total_cost": round(max(remaining_cost, 0), 2),
                        "updated_at": now
                    }
                }
            )

        return {
            "id": str(holding["_id"]),
            "code": code,
            "type": "sell",
            "quantity": sell_data.quantity,
            "price": sell_data.price,
            "total": sell_amount,
            "fees": fees["total"],
            "realized_pnl": realized_pnl,
            "remaining_quantity": new_quantity
        }

    @staticmethod
    def delete_holding(user_id: str, code: str) -> bool:
        """删除持仓"""
        db = get_db()
        holdings_collection = db.holdings

        result = holdings_collection.delete_one({
            "user_id": user_id,
            "code": code
        })

        return result.deleted_count > 0

    @staticmethod
    def get_holdings(user_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取持仓列表（不查询实时价格）"""
        db = get_db()
        holdings_collection = db.holdings

        skip = (page - 1) * page_size
        total = holdings_collection.count_documents({"user_id": user_id})

        holdings = list(holdings_collection.find(
            {"user_id": user_id}
        ).skip(skip).limit(page_size))

        items = []
        for h in holdings:
            items.append({
                "id": str(h["_id"]),
                "user_id": h["user_id"],
                "code": h["code"],
                "name": h.get("name"),
                "quantity": h["quantity"],
                "average_cost": h["average_cost"],
                "highest_price": h.get("highest_price"),
                "exit_rule": h.get("exit_rule"),
                "tier_triggered": h.get("tier_triggered"),
                "created_at": h["created_at"],
                "updated_at": h["updated_at"]
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }

    @staticmethod
    def get_holding(user_id: str, code: str) -> Optional[Dict]:
        """获取单个持仓"""
        db = get_db()
        holdings_collection = db.holdings

        holding = holdings_collection.find_one({
            "user_id": user_id,
            "code": code
        })

        if not holding:
            return None

        return {
            "id": str(holding["_id"]),
            "user_id": holding["user_id"],
            "code": holding["code"],
            "name": holding.get("name"),
            "quantity": holding["quantity"],
            "average_cost": holding["average_cost"],
            "highest_price": holding.get("highest_price"),
            "exit_rule": holding.get("exit_rule"),
            "tier_triggered": holding.get("tier_triggered"),
            "created_at": holding["created_at"],
            "updated_at": holding["updated_at"]
        }

    @staticmethod
    def update_exit_rule(user_id: str, code: str, exit_rule: ExitRuleRequest) -> Optional[Dict]:
        """更新卖出规则"""
        db = get_db()
        holdings_collection = db.holdings

        holding = holdings_collection.find_one({
            "user_id": user_id,
            "code": code
        })

        if not holding:
            return None

        exit_rule_dict = {
            "exit_strategy": exit_rule.exit_strategy,
            "stop_loss": exit_rule.stop_loss,
            "profit_target": exit_rule.profit_target,
            "trailing_stop_pct": exit_rule.trailing_stop_pct,
            "tier_profits": exit_rule.tier_profits,
            "tier_sell_pcts": exit_rule.tier_sell_pcts
        }

        holdings_collection.update_one(
            {"_id": holding["_id"]},
            {
                "$set": {
                    "exit_rule": exit_rule_dict,
                    "updated_at": datetime.now()
                }
            }
        )

        return HoldingService.get_holding(user_id, code)

    @staticmethod
    def get_all_holdings(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """管理员获取所有用户持仓"""
        db = get_db()
        holdings_collection = db.holdings

        skip = (page - 1) * page_size
        total = holdings_collection.count_documents({})

        holdings = list(holdings_collection.find().skip(skip).limit(page_size))

        items = []
        for h in holdings:
            current_price = get_stock_price(h["code"])
            market_value = current_price * h["quantity"] if current_price else None

            items.append({
                "id": str(h["_id"]),
                "user_id": h["user_id"],
                "code": h["code"],
                "name": h.get("name"),
                "quantity": h["quantity"],
                "average_cost": h["average_cost"],
                "current_price": current_price,
                "market_value": round(market_value, 2) if market_value else None
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }