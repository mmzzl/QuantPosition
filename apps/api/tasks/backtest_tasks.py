from datetime import datetime, timedelta
from typing import Dict, Any, List
from celery_config import celery_app
from database import get_db
from bin.rule_engine import StockRuleEngine


@celery_app.task(bind=True, name="tasks.backtest.run_simple")
def run_simple_backtest(
    self,
    strategy: str = "dual_ma",
    days_back: int = 180,
    hold_days: List[int] = None,
) -> Dict[str, Any]:
    if hold_days is None:
        hold_days = [5, 20, 60]

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载选股数据..."})

    db = get_db()
    if strategy == "dual_ma":
        raw = list(db.stock_selections.find({"strategy": "dual_moving_average"}).sort("selection_date", -1).limit(500))
    else:
        raw = list(db.news_selection_cache.find({}).sort("created_at", -1).limit(500))

    cutoff = datetime.now() - timedelta(days=days_back)
    selections = []
    for s in raw:
        d = s.get("selection_date") or s.get("created_at")
        if d and d >= cutoff:
            selections.append(s)

    total = len(selections)
    self.update_state(state="PROGRESS", meta={"current": 0, "total": total, "status": f"共{total}个信号，开始回测..."})

    trades_flat = {d: [] for d in hold_days}
    stats = {}

    for idx, sel in enumerate(selections):
        if idx % 20 == 0:
            self.update_state(state="PROGRESS", meta={
                "current": idx, "total": total,
                "status": f"回测中 {idx}/{total}..."
            })

        code = sel["code"]
        name = sel.get("name", "")
        buy_date = sel.get("selection_date") or sel.get("created_at")
        buy_price = sel.get("current_price") or sel.get("price", 0)
        if not buy_price or buy_price <= 0 or not buy_date:
            continue

        buy_day = buy_date.strftime("%Y-%m-%d") if isinstance(buy_date, datetime) else str(buy_date)[:10]
        end_day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        klines = list(db.stock_kline.find({
            "code": code,
            "date": {"$gte": f"{buy_day} 15:00", "$lte": f"{end_day} 15:00"},
            "frequency": 9,
        }).sort("date", 1))

        if not klines:
            continue

        max_hold = max(hold_days)
        for days in hold_days:
            if len(klines) >= days:
                sp = klines[days - 1]["close"]
                ret = round((sp - buy_price) / buy_price * 100, 2)
                trades_flat[days].append({
                    "code": code, "name": name,
                    "buy_date": buy_day, "buy_price": round(buy_price, 2),
                    "sell_date": klines[days - 1]["date"][:10],
                    "sell_price": round(sp, 2),
                    "return_pct": ret,
                })

        if len(klines) >= max_hold:
            prices = [k["close"] for k in klines[:max_hold]]
            peak = max(prices)
            trough = min(prices)
            dd = round((trough - peak) / peak * 100, 2) if peak else 0
            stats[code] = {
                "buy_price": round(buy_price, 2),
                "final_price": round(prices[-1], 2),
                "return_pct": round((prices[-1] - buy_price) / buy_price * 100, 2),
                "max_drawdown": dd,
            }

    result = {}
    for d in hold_days:
        trades = trades_flat[d]
        if not trades:
            result[f"{d}d"] = {"trades": 0}
            continue
        returns = [t["return_pct"] for t in trades]
        wins = sum(1 for r in returns if r > 0)
        result[f"{d}d"] = {
            "trades": len(trades),
            "win_rate": round(wins / len(trades) * 100, 1),
            "avg_return": round(sum(returns) / len(returns), 2),
            "total_return": round(sum(returns), 2),
            "best_return": max(returns),
            "worst_return": min(returns),
            "examples": trades[:10],
        }

    if stats:
        all_returns = [s["return_pct"] for s in stats.values()]
        all_dds = [s["max_drawdown"] for s in stats.values()]
        result["summary"] = {
            "stocks": len(stats),
            "avg_return": round(sum(all_returns) / len(all_returns), 2),
            "avg_max_drawdown": round(sum(all_dds) / len(all_dds), 2),
        }

    self.update_state(state="PROGRESS", meta={
        "current": total, "total": total, "status": "回测完成"
    })

    return {"strategy": strategy, "days_back": days_back, "selections_analyzed": len(selections), "results": result}


@celery_app.task(bind=True, name="tasks.backtest.run_with_rules")
def run_rule_backtest(
    self,
    days_back: int = 180,
) -> Dict[str, Any]:
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载规则和选股数据..."})

    db = get_db()
    rules = list(db.trading_rules.find({"enabled": True, "type": {"$in": ["sell", "risk"]}}).sort("rule_id", 1))
    if not rules:
        return {"error": "no enabled sell/risk rules"}

    engine = StockRuleEngine(rules)
    cutoff = datetime.now() - timedelta(days=days_back)
    raw = list(db.news_selection_cache.find({}).sort("created_at", -1).limit(300))
    selections = [s for s in raw if s.get("created_at", datetime.min) >= cutoff]
    total = len(selections)

    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": total,
        "status": f"共{total}个信号，加载{len(rules)}条规则，开始模拟..."
    })

    trades = []
    for idx, sel in enumerate(selections):
        if idx % 10 == 0:
            self.update_state(state="PROGRESS", meta={
                "current": idx, "total": total,
                "status": f"规则回测 {idx}/{total}..."
            })

        code = sel["code"]
        name = sel.get("name", "")
        buy_date = sel.get("created_at")
        buy_price = sel.get("current_price") or sel.get("price", 0)
        if not buy_price or buy_price <= 0 or not isinstance(buy_date, datetime):
            continue

        buy_day = buy_date.strftime("%Y-%m-%d")
        klines = list(db.stock_kline.find({
            "code": code,
            "date": {"$gte": f"{buy_day} 15:00"},
            "frequency": 9,
        }).sort("date", 1).limit(120))
        if len(klines) < 2:
            continue

        closes, volumes = [], []
        exit_info = None
        for i, k in enumerate(klines):
            closes.append(k["close"])
            volumes.append(k["volume"])
            if i == 0:
                continue
            stock_data = {
                "close": closes[-1], "volume": volumes[-1],
                "ma5": sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1],
                "ma10": sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1],
                "ma5_vol": sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1],
                "last_close": closes[-2],
                "high": max(c["high"] for c in klines[max(0, i - 19):i + 1]),
                "low": min(c["low"] for c in klines[max(0, i - 19):i + 1]),
                "open": k["open"], "name": name,
            }
            position = {
                "has_pos": True, "cost": buy_price,
                "buy_date": buy_date.date() if isinstance(buy_date, datetime) else buy_date,
            }
            ctx = StockRuleEngine.build_context(stock_data, position)
            _, sell_score, _, triggered = engine.run(ctx)
            if sell_score > 0:
                exit_info = {
                    "exit_date": k["date"], "exit_price": round(closes[-1], 2),
                    "return_pct": round((closes[-1] - buy_price) / buy_price * 100, 2),
                    "triggered_rules": [r["name"] for r in triggered],
                    "hold_days": i,
                }
                break

        if exit_info:
            trades.append({
                "code": code, "name": name, "buy_date": buy_day,
                "buy_price": round(buy_price, 2), **exit_info,
            })

    if not trades:
        return {"trades": 0, "message": "no trades simulated"}

    returns = [t["return_pct"] for t in trades]
    wins = sum(1 for r in returns if r > 0)
    hold_days_list = [t["hold_days"] for t in trades]

    return {
        "strategy": "rule_engine", "days_back": days_back,
        "rules_used": [r["name"] for r in rules],
        "trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1),
        "avg_return": round(sum(returns) / len(returns), 2),
        "total_return": round(sum(returns), 2),
        "best_return": max(returns),
        "worst_return": min(returns),
        "avg_hold_days": round(sum(hold_days_list) / len(hold_days_list), 0),
        "trade_details": trades[:30],
    }
