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

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载K线数据..."})

    db = get_db()
    today = datetime.now()
    max_hold = max(hold_days) + 5

    # 选取有足够K线数据的股票代码
    all_codes = db.stock_kline.distinct("code", {"frequency": 9})
    total = len(all_codes)

    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": total,
        "status": f"共{total}只股票，扫描金叉信号..."
    })

    # 从 sector_stocks 拿名称
    name_map = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        pure = s["stock_code"].split(".")[-1]
        name_map[pure] = s.get("stock_name", "")

    lookback = days_back + max_hold
    start_str = (today - timedelta(days=lookback)).strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    signals = []
    for idx, code in enumerate(all_codes):
        if idx % 200 == 0:
            self.update_state(state="PROGRESS", meta={
                "current": idx, "total": total,
                "status": f"扫描 {idx}/{total} ..."
            })

        klines = list(db.stock_kline.find({
            "code": code, "frequency": 9,
            "date": {"$gte": f"{start_str} 15:00", "$lte": f"{end_str} 15:00"},
        }).sort("date", 1))

        if len(klines) < 25:
            continue

        closes = [k["close"] for k in klines]
        dates = [k["date"] for k in klines]

        name = name_map.get(code, "")
        if name.startswith("ST") or name.startswith("*ST"):
            continue

        # 查找金叉：短均线上穿长均线
        for i in range(20, len(klines) - max_hold):
            short_ma = sum(closes[i - 5:i]) / 5
            long_ma = sum(closes[i - 20:i]) / 20
            prev_short = sum(closes[i - 6:i - 1]) / 5
            prev_long = sum(closes[i - 21:i - 1]) / 20

            if prev_short <= prev_long and short_ma > long_ma:
                buy_price = closes[i]
                buy_day = dates[i][:10]
                signals.append({
                    "code": code,
                    "name": name,
                    "buy_day": buy_day,
                    "buy_price": buy_price,
                    "signal_idx": i,
                })
                break

    total_signals = len(signals)
    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": total_signals,
        "status": f"找到{total_signals}个金叉信号，开始回测..."
    })

    trades_flat = {d: [] for d in hold_days}
    stats = {}

    for idx, sig in enumerate(signals):
        if idx % 20 == 0:
            self.update_state(state="PROGRESS", meta={
                "current": idx, "total": total_signals,
                "status": f"回测 {idx}/{total_signals} ..."
            })

        code = sig["code"]
        buy_price = sig["buy_price"]
        buy_day = sig["buy_day"]
        end_day = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        klines = list(db.stock_kline.find({
            "code": code, "frequency": 9,
            "date": {"$gte": f"{buy_day} 15:00", "$lte": f"{end_day} 15:00"},
        }).sort("date", 1))

        if len(klines) < max_hold:
            continue

        for days in hold_days:
            if len(klines) >= days:
                sp = klines[days - 1]["close"]
                ret = round((sp - buy_price) / buy_price * 100, 2)
                trades_flat[days].append({
                    "code": code, "name": sig["name"],
                    "buy_date": buy_day, "buy_price": round(buy_price, 2),
                    "sell_date": klines[days - 1]["date"][:10],
                    "sell_price": round(sp, 2), "return_pct": ret,
                })

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
            "best": max(returns),
            "worst": min(returns),
            "examples": trades[:10],
        }

    if stats:
        all_ret = [s["return_pct"] for s in stats.values()]
        all_dd = [s["max_drawdown"] for s in stats.values()]
        result["summary"] = {
            "stocks": len(stats),
            "avg_return": round(sum(all_ret) / len(all_ret), 2),
            "avg_max_drawdown": round(sum(all_dd) / len(all_dd), 2),
        }

    return {
        "strategy": "dual_ma",
        "days_back": days_back,
        "signal_count": total_signals,
        "results": result,
    }


@celery_app.task(bind=True, name="tasks.backtest.run_with_rules")
def run_rule_backtest(
    self,
    days_back: int = 180,
) -> Dict[str, Any]:
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载规则..."})

    db = get_db()
    rules = list(db.trading_rules.find({"enabled": True, "type": {"$in": ["sell", "risk"]}}).sort("rule_id", 1))
    if not rules:
        return {"error": "no enabled sell/risk rules"}

    engine = StockRuleEngine(rules)
    today = datetime.now()

    # 用 news_selection_cache 作为买入信号源
    raw = list(db.news_selection_cache.find({}).sort("created_at", -1))
    cutoff = today - timedelta(days=days_back)
    selections = [s for s in raw if s.get("created_at", datetime.min) >= cutoff]
    total = len(selections)

    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": total,
        "status": f"共{total}个新闻选股信号，加载{len(rules)}条规则..."
    })

    trades = []
    for idx, sel in enumerate(selections):
        if idx % 10 == 0:
            self.update_state(state="PROGRESS", meta={
                "current": idx, "total": total,
                "status": f"回测 {idx}/{total}..."
            })

        code = sel["code"]
        name = sel.get("name", "")
        buy_date = sel.get("created_at")
        buy_price = sel.get("current_price") or sel.get("price", 0)
        if not buy_price or buy_price <= 0 or not isinstance(buy_date, datetime):
            continue
        if buy_date >= today - timedelta(days=5):
            continue

        buy_day = buy_date.strftime("%Y-%m-%d")
        klines = list(db.stock_kline.find({
            "code": code, "frequency": 9,
            "date": {"$gte": f"{buy_day} 15:00"},
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
            sd = {
                "close": closes[-1], "volume": volumes[-1],
                "ma5": sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1],
                "ma10": sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1],
                "ma5_vol": sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1],
                "last_close": closes[-2],
                "high": max(c["high"] for c in klines[max(0, i - 19):i + 1]),
                "low": min(c["low"] for c in klines[max(0, i - 19):i + 1]),
                "open": k["open"], "name": name,
            }
            pos = {"has_pos": True, "cost": buy_price, "buy_date": buy_date.date()}
            ctx = StockRuleEngine.build_context(sd, pos)
            _, sell_score, _, triggered = engine.run(ctx)
            if sell_score > 0:
                exit_info = {
                    "exit_date": k["date"],
                    "exit_price": round(closes[-1], 2),
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
        "best": max(returns),
        "worst": min(returns),
        "avg_hold_days": round(sum(hold_days_list) / len(hold_days_list), 0),
        "trade_details": trades[:30],
    }
