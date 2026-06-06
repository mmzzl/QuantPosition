from bson import ObjectId
from datetime import datetime
from typing import Optional, List, Dict
from database import get_db


class TransactionService:
    """交易记录服务"""

    @staticmethod
    def create_transaction(user_id: str, code: str, trans_type: str, quantity: int, price: float) -> Dict:
        """创建交易记录"""
        db = get_db()
        transactions_collection = db.transactions

        total = quantity * price
        now = datetime.now()

        transaction_doc = {
            "user_id": user_id,
            "code": code,
            "type": trans_type,
            "quantity": quantity,
            "price": price,
            "total": total,
            "created_at": now
        }

        result = transactions_collection.insert_one(transaction_doc)

        return {
            "id": str(result.inserted_id),
            "user_id": user_id,
            "code": code,
            "type": trans_type,
            "quantity": quantity,
            "price": price,
            "total": total,
            "created_at": now
        }

    @staticmethod
    def get_transactions(user_id: str, page: int = 1, page_size: int = 20) -> Dict:
        """获取交易记录列表"""
        db = get_db()
        transactions_collection = db.transactions

        skip = (page - 1) * page_size
        total = transactions_collection.count_documents({"user_id": user_id})

        transactions = list(transactions_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(page_size))

        items = []
        for t in transactions:
            items.append({
                "id": str(t["_id"]),
                "user_id": t["user_id"],
                "code": t["code"],
                "type": t["type"],
                "quantity": t["quantity"],
                "price": t["price"],
                "total": t["total"],
                "created_at": t["created_at"]
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }

    @staticmethod
    def get_history(user_id: str, page: int = 1, page_size: int = 20) -> Dict:
        """获取持仓历史（与 get_transactions 相同）"""
        return TransactionService.get_transactions(user_id, page, page_size)

    @staticmethod
    def delete_transaction(user_id: str, transaction_id: str) -> bool:
        """删除交易记录"""
        db = get_db()
        transactions_collection = db.transactions

        try:
            result = transactions_collection.delete_one({
                "_id": ObjectId(transaction_id),
                "user_id": user_id
            })
            return result.deleted_count > 0
        except Exception:
            return False

    @staticmethod
    def get_realized_pnl(user_id: str) -> float:
        """计算已实现盈亏（累加每笔卖出记录的 realized_pnl）"""
        db = get_db()
        transactions_collection = db.transactions

        sells = list(transactions_collection.find({
            "user_id": user_id,
            "type": "sell"
        }))

        total = 0
        for s in sells:
            if "realized_pnl" in s:
                total += s["realized_pnl"]
            else:
                # 旧数据兼容：按该股买入均价估算
                code = s["code"]
                buys = list(transactions_collection.find({
                    "user_id": user_id,
                    "code": code,
                    "type": "buy"
                }))
                if buys:
                    total_buy_qty = sum(b["quantity"] for b in buys)
                    total_buy_cost = sum(b["total"] for b in buys)
                    avg_cost = total_buy_cost / total_buy_qty if total_buy_qty > 0 else 0
                    cost_of_sold = s["quantity"] * avg_cost
                    total += s["total"] - cost_of_sold

        return round(total, 2)

    @staticmethod
    def get_all_realized_pnl() -> Dict:
        """管理员获取所有用户已实现盈亏（聚合每条卖出记录的 realized_pnl）"""
        db = get_db()
        transactions_collection = db.transactions

        pipeline = [
            {"$match": {"type": "sell", "realized_pnl": {"$exists": True}}},
            {"$group": {"_id": "$user_id", "realized_pnl": {"$sum": "$realized_pnl"}}}
        ]

        results = list(transactions_collection.aggregate(pipeline))

        return {
            "users": [{"user_id": r["_id"], "realized_pnl": round(r["realized_pnl"], 2)} for r in results],
            "total_realized_pnl": round(sum(r["realized_pnl"] for r in results), 2)
        }