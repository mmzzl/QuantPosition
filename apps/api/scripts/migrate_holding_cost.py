import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from database import get_db

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import settings


def _is_shanghai(code: str) -> bool:
    return code.startswith("60") or code.startswith("688")


def calc_buy_fees(price: float, quantity: int, code: str) -> float:
    amount = price * quantity
    commission = max(amount * settings.commission_rate, settings.min_commission)
    transfer_fee = amount * settings.transfer_rate if _is_shanghai(code) else 0
    return round(commission + transfer_fee, 2)


def migrate_holdings():
    db = get_db()

    # 1. 迁移持仓：补上 total_cost
    holdings_fixed = 0
    for h in db.holdings.find({"total_cost": {"$exists": False}}):
        total_cost = round(h["quantity"] * h["average_cost"], 2)
        db.holdings.update_one(
            {"_id": h["_id"]},
            {"$set": {"total_cost": total_cost}}
        )
        holdings_fixed += 1
    print(f"持仓迁移完成: {holdings_fixed} 条补上 total_cost")

    # 2. 迁移卖出交易：按当时买入均价估算 realized_pnl
    sells_fixed = 0
    for s in db.transactions.find({"type": "sell", "realized_pnl": {"$exists": False}}):
        code = s["code"]
        user_id = s["user_id"]
        sell_date = s["created_at"]

        # 找卖出之前的所有买入
        buys = list(db.transactions.find({
            "user_id": user_id,
            "code": code,
            "type": "buy",
            "created_at": {"$lte": sell_date}
        }).sort("created_at", 1))

        if buys:
            total_qty = sum(b["quantity"] for b in buys)
            total_cost = sum(b["total"] + b.get("fees", 0) for b in buys)
            avg_cost = total_cost / total_qty if total_qty > 0 else 0
            cost_of_sold = s["quantity"] * avg_cost
        else:
            cost_of_sold = 0

        sell_fees = s.get("fees", 0)
        sell_net = s["total"] - sell_fees
        realized_pnl = round(sell_net - cost_of_sold, 2)

        db.transactions.update_one(
            {"_id": s["_id"]},
            {"$set": {"realized_pnl": realized_pnl}}
        )
        sells_fixed += 1
    print(f"卖出交易迁移完成: {sells_fixed} 条补上 realized_pnl")

    print("\n迁移完成。请重启后端服务。")


if __name__ == "__main__":
    migrate_holdings()
