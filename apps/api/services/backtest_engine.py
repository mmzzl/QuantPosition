import backtrader as bt
import pandas as pd
from datetime import datetime, date as date_cls
from typing import Dict, Any, List, Optional
from database import get_db


class RuleStrategy(bt.Strategy):
    """规则驱动策略：从 MongoDB 加载规则，每根 K 线调用规则引擎决策"""

    params = dict(stop_loss_pct=0.08, max_hold_days=60)

    def __init__(self):
        from bin.rule_engine import StockRuleEngine

        db = get_db()
        rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))
        self.engine = StockRuleEngine(rules) if rules else None

        self.sma5 = bt.indicators.SMA(self.data.close, period=5)
        self.sma10 = bt.indicators.SMA(self.data.close, period=10)
        self.sma_vol5 = bt.indicators.SMA(self.data.volume, period=5)
        self.highest20 = bt.indicators.Highest(self.data.high, period=20)
        self.lowest20 = bt.indicators.Lowest(self.data.low, period=20)

        self.entry_price = None
        self.entry_date = None
        self.trades = []
        self.equity = []

    def _build_ctx(self, has_pos, cost, buy_date, today):
        return StockRuleEngine.build_context({
            "close": self.data.close[0],
            "volume": self.data.volume[0],
            "ma5": self.sma5[0],
            "ma10": self.sma10[0],
            "ma5_vol": self.sma_vol5[0],
            "last_close": self.data.close[-1],
            "high": self.highest20[0],
            "low": self.lowest20[0],
            "open": self.data.open[0],
            "name": "",
        }, {"has_pos": has_pos, "cost": cost, "buy_date": buy_date})

    def next(self):
        dt = self.data.datetime.date(0)
        self.equity.append({"date": dt.isoformat(), "value": round(self.broker.getvalue(), 2)})

        if not self.engine or len(self.data) < 20:
            return

        if not self.position:
            ctx = self._build_ctx(False, 0, dt, dt)
            _, _, buy_score, _ = self.engine.run(ctx)
            if buy_score >= 0.5:
                size = int((self.broker.getcash() * 0.95) / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = self.data.close[0]
                    self.entry_date = dt
        else:
            ctx = self._build_ctx(True, self.entry_price, self.entry_date, dt)
            risk, sell_score, _, triggered = self.engine.run(ctx)

            reason = None
            if risk:
                reason = "risk"
            elif sell_score > 0:
                reason = "sell"
            elif (dt - self.entry_date).days >= self.p.max_hold_days:
                reason = "timeout"
            elif self.data.close[0] < self.entry_price * (1 - self.p.stop_loss_pct):
                reason = "stop_loss"

            if reason:
                pnl = round((self.data.close[0] - self.entry_price) / self.entry_price * 100, 2)
                self.sell(size=self.position.size)
                self.trades.append({
                    "entry_date": self.entry_date.isoformat(),
                    "exit_date": dt.isoformat(),
                    "entry_price": round(self.entry_price, 2),
                    "exit_price": round(self.data.close[0], 2),
                    "pnl_pct": pnl,
                    "hold_days": (dt - self.entry_date).days,
                    "reason": reason,
                    "triggered_rules": [r["name"] for r in (triggered or [])],
                })
                self.entry_price = None
                self.entry_date = None


STRATEGIES = {"rule_engine": RuleStrategy}


def _load_klines(code, start, end):
    db = get_db()
    klines = list(db.stock_kline.find({
        "code": code, "frequency": 9,
        "date": {"$gte": f"{start} 15:00", "$lte": f"{end} 15:00"},
    }).sort("date", 1))
    if not klines or len(klines) < 30:
        return None
    rows = [{"datetime": pd.Timestamp(k["date"][:10]),
             "open": float(k["open"]), "high": float(k["high"]),
             "low": float(k["low"]), "close": float(k["close"]),
             "volume": float(k["volume"])} for k in klines]
    df = pd.DataFrame(rows).set_index("datetime")
    return df


def run_backtest(
    strategy_name: str = "rule_engine",
    codes: List[str] = None,
    start_date: str = None,
    end_date: str = None,
    initial_cash: float = 100000,
    commission: float = 0.001,
) -> Dict[str, Any]:

    cls = STRATEGIES.get(strategy_name)
    if not cls:
        return {"error": f"未知策略: {strategy_name}"}

    if not start_date:
        start_date = (datetime.now() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    db = get_db()
    if not codes:
        codes = db.stock_kline.distinct("code", {"frequency": 9})

    name_map = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        pure = s["stock_code"].split(".")[-1]
        name_map[pure] = s.get("stock_name", "")

    filtered = [c for c in codes if not name_map.get(c, "").startswith(("ST", "*ST"))]

    all_trades = []
    all_equity = []
    processed = 0
    skipped = 0

    for code in filtered:
        df = _load_klines(code, start_date, end_date)
        if df is None:
            skipped += 1
            continue

        cerebro = bt.Cerebro()
        cerebro.addstrategy(cls)
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=commission)

        try:
            strat = cerebro.run()[0]
            for t in strat.trades:
                t["code"] = code
                t["name"] = name_map.get(code, "")
            all_trades.extend(strat.trades)
            all_equity.extend(strat.equity)
            processed += 1
        except Exception:
            skipped += 1

    if not all_trades:
        return {"strategy": strategy_name, "trades": 0, "processed": processed, "skipped": skipped}

    pnls = [t["pnl_pct"] for t in all_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    import statistics

    exit_stats = {}
    for t in all_trades:
        exit_stats[t["reason"]] = exit_stats.get(t["reason"], 0) + 1

    sharpe = round(statistics.mean(pnls) / statistics.stdev(pnls) * (252 ** 0.5), 2) \
        if len(pnls) > 1 and statistics.stdev(pnls) > 0 else 0

    return {
        "strategy": strategy_name,
        "trades": len(all_trades),
        "processed": processed,
        "skipped": skipped,
        "win_rate": round(len(wins) / len(pnls) * 100, 1),
        "avg_return": round(sum(pnls) / len(pnls), 2),
        "total_return": round(sum(pnls), 2),
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else 99,
        "sharpe": sharpe,
        "exit_stats": exit_stats,
        "examples": all_trades[:10],
    }
