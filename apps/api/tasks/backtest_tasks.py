from datetime import datetime, timedelta
from typing import Dict, Any, List
from celery_config import celery_app
from database import get_db
from bin.rule_engine import StockRuleEngine


def _save(name: str, data: dict):
    try:
        db = get_db()
        db.backtest_results.replace_one(
            {"_id": "latest"},
            {**data, "name": name, "saved_at": datetime.now()},
            upsert=True,
        )
    except Exception:
        pass


@celery_app.task(bind=True, name="tasks.backtest.run_simple")
def run_simple_backtest(
    self,
    strategy: str = "dual_ma",
    days_back: int = 180,
    hold_days: List[int] = None,
    use_rules: bool = False,
) -> Dict[str, Any]:
    if hold_days is None:
        hold_days = [5, 20, 60]

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 0, "status": "加载数据..."})

    db = get_db()
    today = datetime.now()
    max_hold = max(hold_days) + 5

    rules_loaded = None
    rule_engine = None
    if use_rules:
        rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))
        if rules:
            rule_engine = StockRuleEngine(rules)
            rules_loaded = [r["name"] for r in rules]
            self.update_state(state="PROGRESS", meta={
                "current": 0, "total": 0,
                "status": f"加载{len(rules)}条规则，开始回测..."
            })

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

    import statistics

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

        i = 20
        while i < len(klines) - max_hold:
            short_ma = sum(closes[i - 5:i]) / 5
            long_ma = sum(closes[i - 20:i]) / 20
            prev_short = sum(closes[i - 6:i - 1]) / 5
            prev_long = sum(closes[i - 21:i - 1]) / 20

            if prev_short <= prev_long and short_ma > long_ma:
                signals.append({
                    "code": code, "name": name,
                    "buy_day": dates[i][:10],
                    "buy_price": closes[i],
                    "signal_idx": i,
                })
                i += 20
            else:
                i += 1

    total_signals = len(signals)
    self.update_state(state="PROGRESS", meta={
        "current": 0, "total": total_signals,
        "status": f"找到{total_signals}个金叉信号，开始回测..."
    })

    all_trades = []
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
        if not klines:
            continue

        if rule_engine:
            # ===== 规则引擎路径：买入规则确认 + 卖出规则退出 =====
            closes = [k["close"] for k in klines]
            volumes = [k["volume"] for k in klines]

            # 信号日运行买入规则做确认
            day0_sd = {
                "close": closes[0], "volume": volumes[0],
                "ma5": sum(closes[:5]) / 5 if len(closes) >= 5 else closes[0],
                "ma10": sum(closes[:10]) / 10 if len(closes) >= 10 else closes[0],
                "ma5_vol": sum(volumes[:5]) / 5 if len(volumes) >= 5 else volumes[0],
                "last_close": closes[0], "high": closes[0], "low": closes[0],
                "open": klines[0]["open"], "name": sig["name"],
            }
            pos = {"has_pos": False, "cost": 0, "buy_date": today.date()}
            ctx = StockRuleEngine.build_context(day0_sd, pos)
            _, _, buy_score, _ = rule_engine.run(ctx)
            if buy_score < 0.5:
                continue

            # 买入后逐日运行卖出/风控规则
            exit_info = None
            for i in range(1, len(klines)):
                sd = {
                    "close": closes[i], "volume": volumes[i],
                    "ma5": sum(closes[max(0, i - 4):i + 1]) / min(5, i + 1),
                    "ma10": sum(closes[max(0, i - 9):i + 1]) / min(10, i + 1),
                    "ma5_vol": sum(volumes[max(0, i - 4):i + 1]) / min(5, i + 1),
                    "last_close": closes[i - 1],
                    "high": max(k["high"] for k in klines[max(0, i - 19):i + 1]),
                    "low": min(k["low"] for k in klines[max(0, i - 19):i + 1]),
                    "open": klines[i]["open"], "name": sig["name"],
                }
                pos = {"has_pos": True, "cost": buy_price, "buy_date": today.date()}
                ctx = StockRuleEngine.build_context(sd, pos)
                risk, sell_sc, _, triggered = rule_engine.run(ctx)
                if risk or sell_sc > 0:
                    exit_info = {
                        "exit_day": i, "exit_price": closes[i],
                        "triggered_rules": [r["name"] for r in triggered],
                        "risk_triggered": risk,
                    }
                    break

            if exit_info:
                ret = round((exit_info["exit_price"] - buy_price) / buy_price * 100, 2)
                all_trades.append({
                    "code": code, "name": sig["name"],
                    "buy_date": buy_day, "buy_price": round(buy_price, 2),
                    "sell_date": klines[exit_info["exit_day"]]["date"][:10],
                    "sell_price": round(exit_info["exit_price"], 2),
                    "return_pct": ret, "hold_days": exit_info["exit_day"],
                    "triggered_rules": exit_info["triggered_rules"],
                    "risk_triggered": exit_info["risk_triggered"],
                })
            elif len(klines) >= max_hold:
                ret = round((klines[max_hold - 1]["close"] - buy_price) / buy_price * 100, 2)
                all_trades.append({
                    "code": code, "name": sig["name"],
                    "buy_date": buy_day, "buy_price": round(buy_price, 2),
                    "sell_date": klines[max_hold - 1]["date"][:10],
                    "sell_price": round(klines[max_hold - 1]["close"], 2),
                    "return_pct": ret, "hold_days": max_hold,
                    "triggered_rules": [], "risk_triggered": False,
                })
        else:
            # ===== 无规则路径：固定持有 + 8%硬止损 =====
            stop_pct = 0.08
            exit_day = None
            for i, k in enumerate(klines):
                if min(k["low"], k["close"]) < buy_price * (1 - stop_pct):
                    exit_day = i
                    break

            if exit_day is not None:
                ret = round((klines[exit_day]["close"] - buy_price) / buy_price * 100, 2)
                all_trades.append({
                    "code": code, "name": sig["name"],
                    "buy_date": buy_day, "buy_price": round(buy_price, 2),
                    "sell_date": klines[exit_day]["date"][:10],
                    "sell_price": round(klines[exit_day]["close"], 2),
                    "return_pct": ret, "stopped_out": True, "hold_days": exit_day,
                })
            elif len(klines) >= max_hold:
                ret = round((klines[max_hold - 1]["close"] - buy_price) / buy_price * 100, 2)
                all_trades.append({
                    "code": code, "name": sig["name"],
                    "buy_date": buy_day, "buy_price": round(buy_price, 2),
                    "sell_date": klines[max_hold - 1]["date"][:10],
                    "sell_price": round(klines[max_hold - 1]["close"], 2),
                    "return_pct": ret, "stopped_out": False, "hold_days": max_hold,
                })

    if not all_trades:
        return {"strategy": "dual_ma", "days_back": days_back, "trades": 0}

    returns = [t["return_pct"] for t in all_trades]
    wins = sum(1 for r in returns if r > 0)
    losses = sum(1 for r in returns if r <= 0)
    stopped = sum(1 for t in all_trades if t.get("stopped_out") or t.get("triggered_rules"))
    rule_triggered = sum(1 for t in all_trades if t.get("triggered_rules"))

    win_returns = [r for r in returns if r > 0]
    loss_returns = [r for r in returns if r <= 0]
    avg_win = round(sum(win_returns) / len(win_returns), 2) if win_returns else 0
    avg_loss = round(sum(loss_returns) / len(loss_returns), 2) if loss_returns else 0

    profit_factor = round(abs(sum(win_returns) / sum(loss_returns)), 2) if sum(loss_returns) != 0 else 99
    sharpe = round(statistics.mean(returns) / statistics.stdev(returns) * (252 ** 0.5), 2) if len(returns) > 1 and statistics.stdev(returns) > 0 else 0

    result = {
        "trades": len(all_trades),
        "win_rate": round(wins / len(all_trades) * 100, 1),
        "avg_return": round(sum(returns) / len(returns), 2),
        "total_return": round(sum(returns), 2),
        "best": max(returns),
        "worst": min(returns),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "sharpe": sharpe,
        "stopped_out": stopped,
        "rule_triggered": rule_triggered,
        "rules_loaded": rules_loaded,
        "max_hold_days": max_hold,
        "examples": [t for t in all_trades[:10]],
    }

    ret = {
        "strategy": "dual_ma",
        "days_back": days_back,
        "signal_count": total_signals,
        "rules_loaded": bool(rules_loaded),
        "results": result,
    }
    _save("dual_ma", ret)
    return ret


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
