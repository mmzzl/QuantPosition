from bson import ObjectId
from datetime import datetime
from typing import Optional, List, Dict, Any
from database import get_db
from models.holding import HoldingCreate, HoldingUpdate, SellRequest, ExitRuleRequest
from utils.stock_api import get_stock_price, get_stock_name


class HoldingService:
    """持仓服务"""

    @staticmethod
    def create_holding(user_id: str, holding_data: HoldingCreate) -> Dict[str, Any]:
        """创建持仓"""
        db = get_db()
        holdings_collection = db.holdings

        # 检查是否已存在该股票的持仓
        existing = holdings_collection.find_one({
            "user_id": user_id,
            "code": holding_data.code
        })

        if existing:
            # 累加数量，重新计算平均成本
            new_quantity = existing["quantity"] + holding_data.quantity
            new_avg_cost = (
                (existing["quantity"] * existing["average_cost"] +
                 holding_data.quantity * holding_data.average_cost)
                / new_quantity
            )

            holdings_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "average_cost": new_avg_cost,
                        "updated_at": datetime.now()
                    }
                }
            )

            # 记录交易历史
            transactions_collection = db.transactions
            transactions_collection.insert_one({
                "user_id": user_id,
                "code": holding_data.code,
                "type": "buy",
                "quantity": holding_data.quantity,
                "price": holding_data.average_cost,
                "total": holding_data.quantity * holding_data.average_cost,
                "created_at": datetime.now()
            })

            # 获取股票名称
            name = holding_data.name or get_stock_name(holding_data.code)

            return {
                "id": str(existing["_id"]),
                "user_id": user_id,
                "code": holding_data.code,
                "name": name,
                "quantity": new_quantity,
                "average_cost": round(new_avg_cost, 2)
            }

        # 获取股票名称
        name = holding_data.name or get_stock_name(holding_data.code)

        # 创建新持仓
        now = datetime.now()
        holding_doc = {
            "user_id": user_id,
            "code": holding_data.code,
            "name": name,
            "quantity": holding_data.quantity,
            "average_cost": holding_data.average_cost,
            "highest_price": holding_data.average_cost,
            "exit_rule": None,
            "tier_triggered": [False, False, False, False],
            "created_at": now,
            "updated_at": now
        }

        result = holdings_collection.insert_one(holding_doc)

        # 记录交易历史
        transactions_collection = db.transactions
        transactions_collection.insert_one({
            "user_id": user_id,
            "code": holding_data.code,
            "type": "buy",
            "quantity": holding_data.quantity,
            "price": holding_data.average_cost,
            "total": holding_data.quantity * holding_data.average_cost,
            "created_at": datetime.now()
        })

        return {
            "id": str(result.inserted_id),
            "user_id": user_id,
            "code": holding_data.code,
            "name": name,
            "quantity": holding_data.quantity,
            "average_cost": holding_data.average_cost
        }

    @staticmethod
    def sell_holding(user_id: str, code: str, sell_data: SellRequest) -> Dict[str, Any]:
        """卖出持仓"""
        db = get_db()
        holdings_collection = db.holdings
        transactions_collection = db.transactions

        # 获取持仓
        holding = holdings_collection.find_one({
            "user_id": user_id,
            "code": code
        })

        if not holding:
            raise ValueError("持仓不存在")

        if holding["quantity"] < sell_data.quantity:
            raise ValueError(f"持仓数量不足，当前持有 {holding['quantity']} 股")

        # 计算卖出总额
        total = sell_data.quantity * sell_data.price

        # 记录交易
        now = datetime.now()
        transaction_doc = {
            "user_id": user_id,
            "code": code,
            "type": "sell",
            "quantity": sell_data.quantity,
            "price": sell_data.price,
            "total": total,
            "created_at": now
        }
        transactions_collection.insert_one(transaction_doc)

        # 更新持仓数量
        new_quantity = holding["quantity"] - sell_data.quantity

        if new_quantity == 0:
            # 删除持仓
            holdings_collection.delete_one({"_id": holding["_id"]})
            return {
                "id": str(holding["_id"]),
                "code": code,
                "type": "sell",
                "quantity": sell_data.quantity,
                "price": sell_data.price,
                "total": total,
                "remaining_quantity": 0
            }
        else:
            # 更新持仓
            holdings_collection.update_one(
                {"_id": holding["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
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
                "total": total,
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