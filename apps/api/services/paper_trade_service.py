import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import get_db
from utils.stock_api import get_stock_price

logger = logging.getLogger(__name__)

PAPER_HOLDINGS = "paper_holdings"
PAPER_TRADES = "paper_trades"
DEFAULT_QUANTITY = 100
CUTOFF_DAYS = 3


class PaperTradingService:

    @staticmethod
    def sync_buy() -> Dict[str, int]:
        db = get_db()
        now = datetime.now()
        cutoff = now - timedelta(days=CUTOFF_DAYS)

        news = list(db.news_selection_cache.find(
            {"created_at": {"$gte": cutoff}}
        ).sort("expected_return", -1).limit(50))

        dual_ma = list(db.stock_selections.find(
            {"selection_date": {"$gte": cutoff}}
        ).sort("selection_date", -1).limit(50))

        sources = [(s, "news") for s in news] + [(s, "dual_ma") for s in dual_ma]

        synced_count = 0
        for sel, strategy in sources:
            code = sel.get("code", "")
            if not code:
                continue

            name = sel.get("name", "")
            price_data = get_stock_price(code)
            if not price_data or price_data <= 0:
                continue

            buy_price = round(float(price_data), 2)
            quantity = DEFAULT_QUANTITY

            existing = db[PAPER_HOLDINGS].find_one({"code": code})
            if existing:
                old_total = existing["avg_cost"] * existing["quantity"]
                new_qty = existing["quantity"] + quantity
                new_avg = round((old_total + buy_price * quantity) / new_qty, 4)
                db[PAPER_HOLDINGS].update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "quantity": new_qty,
                        "avg_cost": new_avg,
                        "updated_at": now,
                    }}
                )
            else:
                db[PAPER_HOLDINGS].insert_one({
                    "code": code,
                    "name": name,
                    "quantity": quantity,
                    "avg_cost": buy_price,
                    "strategy": strategy,
                    "created_at": now,
                    "updated_at": now,
                })

            db[PAPER_TRADES].insert_one({
                "code": code,
                "type": "buy",
                "quantity": quantity,
                "price": buy_price,
                "created_at": now,
            })
            synced_count += 1

        return {"synced_count": synced_count}

    @staticmethod
    def sync_sell() -> None:
        try:
            from bin.rule_engine import StockRuleEngine
        except ImportError as e:
            logger.warning("StockRuleEngine not available, skipping sync_sell: %s", e)
            return

        db = get_db()
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        rules = list(db.trading_rules.find(
            {"enabled": True, "type": {"$in": ["sell", "risk"]}}
        ).sort("rule_id", 1))
        if not rules:
            logger.info("No sell/risk rules found, skipping sync_sell")
            return

        try:
            engine = StockRuleEngine(rules)
        except Exception as e:
            logger.warning("Failed to init StockRuleEngine: %s", e)
            return

        holdings = list(db[PAPER_HOLDINGS].find({}))
        for h in holdings:
            code = h["code"]
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
                "name": h.get("name", ""),
            }
            position = {
                "has_pos": True,
                "cost": h["avg_cost"],
                "buy_date": h.get("created_at").date() if isinstance(h.get("created_at"), datetime) else now.date(),
            }

            try:
                ctx = StockRuleEngine.build_context(stock_data, position)
                _, sell_score, _, triggered = engine.run(ctx)
            except Exception as e:
                logger.warning("Rule engine error for %s: %s", code, e)
                continue

            if sell_score > 0:
                sell_price = closes[-1]
                ret = round((sell_price - h["avg_cost"]) / h["avg_cost"] * 100, 2)

                db[PAPER_TRADES].insert_one({
                    "code": code,
                    "type": "sell",
                    "quantity": h["quantity"],
                    "price": round(sell_price, 2),
                    "return_pct": ret,
                    "sell_date": today_str,
                    "triggered_rules": [r.get("name", "") for r in triggered],
                    "created_at": now,
                })
                db[PAPER_HOLDINGS].delete_one({"_id": h["_id"]})

    @staticmethod
    def get_positions() -> Dict[str, Any]:
        db = get_db()
        holdings = list(db[PAPER_HOLDINGS].find({}).sort("created_at", -1))

        items = []
        total_cost = 0.0
        market_value = 0.0

        for h in holdings:
            price_data = get_stock_price(h["code"])
            current_price = price_data if price_data and price_data > 0 else h["avg_cost"]
            cost = h["avg_cost"] * h["quantity"]
            mv = current_price * h["quantity"]
            pnl = mv - cost
            pnl_pct = (current_price - h["avg_cost"]) / h["avg_cost"] * 100

            items.append({
                "code": h["code"],
                "name": h.get("name", ""),
                "quantity": h["quantity"],
                "avg_cost": round(h["avg_cost"], 2),
                "current_price": round(current_price, 2),
                "market_value": round(mv, 2),
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "strategy": h.get("strategy", ""),
                "created_at": h.get("created_at"),
            })
            total_cost += cost
            market_value += mv

        trades = list(db[PAPER_TRADES].find(
            {"type": "sell"}
        ).sort("created_at", -1).limit(100))

        closed_items = []
        for t in trades:
            closed_items.append({
                "code": t["code"],
                "buy_price": t.get("buy_price"),
                "sell_price": t.get("price", 0),
                "return_pct": t.get("return_pct", 0),
                "sell_date": t.get("sell_date", ""),
                "triggered_rules": t.get("triggered_rules", []),
            })

        wins = sum(1 for t in trades if t.get("return_pct", 0) > 0)

        return {
            "open": {
                "count": len(items),
                "total_cost": round(total_cost, 2),
                "market_value": round(market_value, 2),
                "positions": items,
            },
            "closed": {
                "count": len(closed_items),
                "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
                "trades": closed_items[:30],
            },
        }

    @staticmethod
    def clear() -> None:
        db = get_db()
        db[PAPER_HOLDINGS].delete_many({})
        db[PAPER_TRADES].delete_many({})
