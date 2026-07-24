import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from database import get_db
from services.rule_service import RuleService

logger = logging.getLogger(__name__)


class RuleEngineService:

    @staticmethod
    def evaluate_rule(rule_id: int, code: str) -> Dict[str, Any]:
        """评估单条规则对特定股票是否触发"""
        from bin.rule_engine import (
            StockRuleEngine, build_stock_indicators, load_stock_klines
        )

        db = get_db()
        rule = db.trading_rules.find_one({"rule_id": rule_id})
        if not rule:
            return {"triggered": False, "reason": "rule not found"}

        klines_map = load_stock_klines(db, [code])
        klines = klines_map.get(code, [])
        if not klines or len(klines) < 20:
            return {"triggered": False, "reason": f"insufficient kline data ({len(klines)} bars)"}

        stock_data, atr = build_stock_indicators(klines)
        engine = StockRuleEngine([rule])
        ctx = engine.build_context(stock_data, {"has_pos": False, "cost": 0, "buy_date": None})
        risk_triggered, sell_score, buy_score, triggered = engine.run(ctx)

        return {
            "triggered": len(triggered) > 0,
            "rule_name": rule.get("name", ""),
            "rule_type": rule.get("type", ""),
            "stock_code": code,
            "price": stock_data.get("close", 0),
            "atr": atr,
        }

    @staticmethod
    def evaluate_all_rules(code: str, has_pos: bool = False,
                           cost: float = 0, buy_date: Optional[datetime] = None) -> Dict[str, Any]:
        """评估所有启用规则对特定股票是否触发"""
        from bin.rule_engine import (
            StockRuleEngine, build_stock_indicators, load_stock_klines
        )

        db = get_db()
        rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))
        if not rules:
            return {"triggered": False, "rules": [], "reason": "no enabled rules"}

        klines_map = load_stock_klines(db, [code])
        klines = klines_map.get(code, [])
        if not klines or len(klines) < 20:
            return {"triggered": False, "rules": [], "reason": f"insufficient kline data ({len(klines)} bars)"}

        stock_data, atr = build_stock_indicators(klines)
        engine = StockRuleEngine(rules)

        position = {"has_pos": has_pos, "cost": cost, "buy_date": buy_date}
        ctx = engine.build_context(stock_data, position)
        risk_triggered, sell_score, buy_score, triggered = engine.run(ctx)

        triggered_rules = [
            {
                "rule_id": r.get("rule_id"),
                "name": r.get("name", ""),
                "type": r.get("type", ""),
                "condition": r.get("condition", ""),
            }
            for r in triggered
        ]

        return {
            "triggered": len(triggered_rules) > 0,
            "triggered_rules": triggered_rules,
            "risk_triggered": risk_triggered,
            "sell_score": round(sell_score, 4),
            "buy_score": round(buy_score, 4),
            "price": stock_data.get("close", 0),
            "atr": atr,
            "has_pos": has_pos,
        }