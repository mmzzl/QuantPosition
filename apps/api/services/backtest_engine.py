import backtrader as bt
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Any, List
from database import get_db


class RuleStrategy(bt.Strategy):
    """规则驱动策略：只负责调用规则引擎做买卖决策，其余交给 Backtrader"""

    params = dict(stop_loss_pct=0.08, max_hold_days=60, stock_code="")

    def __init__(self):
        from bin.rule_engine import StockRuleEngine
        self.code = self.p.stock_code
        db = get_db()
        self.rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))
        self.engine = StockRuleEngine(self.rules) if self.rules else None

        self.sma5 = bt.indicators.SMA(self.data.close, period=5)
        self.sma10 = bt.indicators.SMA(self.data.close, period=10)
        self.sma_vol5 = bt.indicators.SMA(self.data.volume, period=5)
        self.highest20 = bt.indicators.Highest(self.data.high, period=20)
        self.lowest20 = bt.indicators.Lowest(self.data.low, period=20)

        self.entry_price = None
        self.entry_date = None
        self.trade_log = []

    def _ctx(self, has_pos, cost, buy_date, today):
        from bin.rule_engine import StockRuleEngine
        return StockRuleEngine.build_context({
            "close": self.data.close[0], "volume": self.data.volume[0],
            "ma5": self.sma5[0], "ma10": self.sma10[0], "ma5_vol": self.sma_vol5[0],
            "last_close": self.data.close[-1],
            "high": self.highest20[0], "low": self.lowest20[0],
            "open": self.data.open[0], "name": "",
        }, {"has_pos": has_pos, "cost": cost, "buy_date": buy_date})

    def next(self):
        if not self.engine or len(self.data) < 20:
            return
        dt = self.data.datetime.date(0)

        if not self.position:
            _, _, buy_score, triggered = self.engine.run(self._ctx(False, 0, dt, dt))
            if buy_score > 0:
                self.buy()
                self.entry_price = self.data.close[0]
                self.entry_date = dt
                logging.info(f"[BUY] {self.code} {dt} price={self.entry_price:.2f} buy_score={buy_score} rules={[r['name'] for r in triggered]}")
        else:
            risk, sell_score, _, triggered = self.engine.run(self._ctx(True, self.entry_price, self.entry_date, dt))
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
                self.trade_log.append({
                    "code": self.code, "entry_date": self.entry_date.isoformat(),
                    "exit_date": dt.isoformat(), "entry_price": round(self.entry_price, 2),
                    "exit_price": round(self.data.close[0], 2), "pnl_pct": pnl,
                    "hold_days": (dt - self.entry_date).days, "reason": reason,
                    "triggered_rules": [r["name"] for r in (triggered or [])],
                })
                logging.info(f"[SELL] {self.code} {dt} entry={self.entry_price:.2f} exit={self.data.close[0]:.2f} pnl={pnl}% reason={reason} rules={[r['name'] for r in (triggered or [])]}")
                self.sell()
                self.entry_price = None
                self.entry_date = None


def _load_klines(code, start, end):
    db = get_db()
    klines = list(db.stock_kline.find(
        {"code": code, "frequency": 9, "date": {"$gte": f"{start} 15:00", "$lte": f"{end} 15:00"}}
    ).sort("date", 1))
    if not klines or len(klines) < 30:
        return None
    rows = [{"datetime": pd.Timestamp(k["date"][:10]),
             "open": float(k["open"]), "high": float(k["high"]),
             "low": float(k["low"]), "close": float(k["close"]),
             "volume": float(k["volume"])} for k in klines]
    return pd.DataFrame(rows).set_index("datetime")


def run_backtest(strategy_name="rule_engine", codes=None, start_date=None, end_date=None,
                 initial_cash=100000, commission=0.001):

    if not start_date:
        start_date = (datetime.now() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    db = get_db()
    if not codes:
        codes = db.stock_kline.distinct("code", {"frequency": 9})

    name_map = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        name_map[s["stock_code"].split(".")[-1]] = s.get("stock_name", "")

    filtered = [c for c in codes if not name_map.get(c, "").startswith(("ST", "*ST"))]
    logging.info(f"[BACKTEST] {start_date}~{end_date} cash={initial_cash} codes={len(filtered)}")

    all_trades = []
    processed = 0
    skipped = 0

    for i, code in enumerate(filtered):
        if (i + 1) % 500 == 0:
            logging.info(f"[BACKTEST] progress {i+1}/{len(filtered)} processed={processed} skipped={skipped} trades={len(all_trades)}")

        df = _load_klines(code, start_date, end_date)
        if df is None:
            skipped += 1
            continue

        cerebro = bt.Cerebro()
        cerebro.addstrategy(RuleStrategy, stock_code=code)
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=commission)
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="ta")

        try:
            strat = cerebro.run()[0]
            for t in strat.trade_log:
                t["name"] = name_map.get(code, "")
            all_trades.extend(strat.trade_log)
            processed += 1
        except Exception as e:
            logging.error(f"[BACKTEST] error {code}: {e}")
            skipped += 1

    logging.info(f"[BACKTEST] done: processed={processed} skipped={skipped} trades={len(all_trades)}")

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

    result = {
        "strategy": strategy_name, "trades": len(all_trades),
        "processed": processed, "skipped": skipped,
        "win_rate": round(len(wins) / len(pnls) * 100, 1),
        "avg_return": round(sum(pnls) / len(pnls), 2),
        "total_return": round(sum(pnls), 2),
        "best": round(max(pnls), 2), "worst": round(min(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else 99,
        "sharpe": sharpe, "exit_stats": exit_stats, "examples": all_trades[:10],
    }

    logging.info(f"[RESULT] trades={len(all_trades)} win_rate={result['win_rate']}% avg_return={result['avg_return']}% total={result['total_return']}% sharpe={sharpe}")
    logging.info(f"[RESULT] exit_stats={exit_stats} best={result['best']}% worst={result['worst']}% avg_win={result['avg_win']}% avg_loss={result['avg_loss']}%")
    for t in all_trades:
        logging.info(f"[TRADE] {t['code']} {t.get('name','')} buy={t['entry_date']}@{t['entry_price']} sell={t['exit_date']}@{t['exit_price']} pnl={t['pnl_pct']}% hold={t['hold_days']}d reason={t['reason']} rules={t.get('triggered_rules',[])}")

    return result
