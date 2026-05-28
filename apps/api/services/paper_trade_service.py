import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import get_db
from utils.stock_api import get_stock_price


class PaperTradingService:

    @staticmethod
    def sync_from_selections() -> Dict[str, Any]:
        db = get_db()
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        cutoff = now - timedelta(days=3)

        selections = list(db.news_selection_cache.find(
            {"created_at": {"$gte": cutoff}}
        ).sort("expected_return", -1).limit(50))

        dual_ma = list(db.stock_selections.find(
            {"selection_date": {"$gte": cutoff}}
        ).sort("selection_date", -1).limit(50))

        added = 0
        for sel in selections + dual_ma:
            code = sel["code"]
            name = sel.get("name", "")
            expected_ret = sel.get("expected_return", sel.get("change_pct", 0))
            price_data = sel.get("current_price") or get_stock_price(code)
            if not price_data:
                continue

            buy_price = price_data if isinstance(price_data, (int, float)) else 0
            if buy_price <= 0:
                continue

            existing = db.paper_positions.find_one({"code": code, "status": "open"})
            if existing:
                continue

            db.paper_positions.insert_one({
                "code": code,
                "name": name,
                "buy_date": today_str,
                "buy_price": round(buy_price, 2),
                "quantity": 100,
                "status": "open",
                "strategy": "news" if sel in selections else "dual_ma",
                "expected_return": round(expected_ret, 2) if expected_ret else 0,
                "created_at": now,
            })
            added += 1

        return {"synced": added, "total": added + len(list(db.paper_positions.find({"status": "open"})))}

    @staticmethod
    def sync_sell_rules() -> Dict[str, Any]:
        from bin.rule_engine import StockRuleEngine
        db = get_db()
        today_str = datetime.now().strftime("%Y-%m-%d")

        rules = list(db.trading_rules.find({"enabled": True, "type": {"$in": ["sell", "risk"]}}).sort("rule_id", 1))
        if not rules:
            return {"sold": 0, "message": "no sell/risk rules"}

        engine = StockRuleEngine(rules)
        positions = list(db.paper_positions.find({"status": "open"}))
        sold = 0

        for pos in positions:
            code = pos["code"]
            klines = list(db.stock_kline.find(
                {"code": code, "frequency": 9},
                sort=[("date", -1)],
                limit=20,
            ))
            if len(klines) < 2:
                continue

            klines.reverse()
            closes = [k["close"] for k in klines]
            volumes = [k["volume"] for k in klines]
            last = klines[-1]

            stock_data = {
                "close": closes[-1],
                "volume": volumes[-1],
                "ma5": sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1],
                "ma10": sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1],
                "ma5_vol": sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1],
                "last_close": closes[-2],
                "high": max(k["high"] for k in klines),
                "low": min(k["low"] for k in klines),
                "open": last["open"],
                "name": pos.get("name", ""),
            }
            position = {
                "has_pos": True,
                "cost": pos["buy_price"],
                "buy_date": datetime.strptime(pos["buy_date"], "%Y-%m-%d").date() if isinstance(pos["buy_date"], str) else pos["buy_date"],
            }
            ctx = StockRuleEngine.build_context(stock_data, position)
            _, sell_score, _, triggered = engine.run(ctx)

            if sell_score > 0:
                sell_price = closes[-1]
                ret = round((sell_price - pos["buy_price"]) / pos["buy_price"] * 100, 2)
                db.paper_positions.update_one(
                    {"_id": pos["_id"]},
                    {"$set": {
                        "status": "closed",
                        "sell_date": today_str,
                        "sell_price": round(sell_price, 2),
                        "return_pct": ret,
                        "triggered_rules": [r["name"] for r in triggered],
                    }}
                )
                sold += 1

        return {"sold": sold, "open": len(positions) - sold}

    @staticmethod
    def get_positions() -> Dict[str, Any]:
        db = get_db()
        open_positions = list(db.paper_positions.find({"status": "open"}).sort("created_at", -1))
        closed_positions = list(db.paper_positions.find({"status": "closed"}).sort("sell_date", -1).limit(100))

        total_cost = sum(p["buy_price"] * p["quantity"] for p in open_positions)
        market_value = 0

        for p in open_positions:
            live_price = get_stock_price(p["code"])
            current_price = live_price if live_price else p["buy_price"]
            market_value += current_price * p["quantity"]
            p["current_price"] = round(current_price, 2)
            p["unrealized_pnl"] = round((current_price - p["buy_price"]) * p["quantity"], 2)
            p["unrealized_pnl_pct"] = round((current_price - p["buy_price"]) / p["buy_price"] * 100, 2)

        closed_returns = [p.get("return_pct", 0) for p in closed_positions]
        wins = sum(1 for r in closed_returns if r > 0)

        open_list = []
        for p in open_positions:
            open_list.append({
                "code": p["code"],
                "name": p.get("name", ""),
                "buy_date": p["buy_date"],
                "buy_price": p["buy_price"],
                "quantity": p["quantity"],
                "current_price": p.get("current_price", p["buy_price"]),
                "unrealized_pnl": p.get("unrealized_pnl", 0),
                "unrealized_pnl_pct": p.get("unrealized_pnl_pct", 0),
                "strategy": p.get("strategy", ""),
            })

        return {
            "open": {
                "count": len(open_positions),
                "total_cost": round(total_cost, 2),
                "market_value": round(market_value, 2),
                "positions": open_list,
            },
            "closed": {
                "count": len(closed_positions),
                "win_rate": round(wins / len(closed_positions) * 100, 1) if closed_positions else 0,
                "trades": [{
                    "code": p["code"],
                    "name": p.get("name", ""),
                    "buy_date": p["buy_date"],
                    "sell_date": p["sell_date"],
                    "buy_price": p["buy_price"],
                    "sell_price": p["sell_price"],
                    "return_pct": p.get("return_pct", 0),
                    "triggered_rules": p.get("triggered_rules", []),
                } for p in closed_positions[:30]],
            },
        }

    @staticmethod
    def clear_all() -> Dict[str, Any]:
        db = get_db()
        count = db.paper_positions.count_documents({})
        db.paper_positions.delete_many({})
        return {"deleted": count}
