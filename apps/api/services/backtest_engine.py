import backtrader as bt
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
from database import get_db


class DualMAStrategy(bt.Strategy):
    params = dict(
        short_period=5,
        long_period=20,
        stop_loss_pct=0.08,
        use_rules=False,
    )

    def __init__(self):
        self.sma_short = bt.indicators.SMA(self.data.close, period=self.p.short_period)
        self.sma_long = bt.indicators.SMA(self.data.close, period=self.p.long_period)
        self.crossover = bt.indicators.CrossOver(self.sma_short, self.sma_long)

        self.entry_price = None
        self.entry_date = None
        self.trades = []
        self.portfolio_values = []

    def next(self):
        dt = self.data.datetime.date(0)
        val = self.broker.getvalue()
        self.portfolio_values.append({
            "date": dt.isoformat(),
            "value": round(val, 2),
        })

        if not self.position:
            if self.crossover > 0:
                size = int((self.broker.getcash() * 0.95) / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = self.data.close[0]
                    self.entry_date = dt
        else:
            exit_reason = None
            if self.crossover < 0:
                exit_reason = "death_cross"
            elif self.data.close[0] < self.entry_price * (1 - self.p.stop_loss_pct):
                exit_reason = "stop_loss"

            if exit_reason:
                sell_price = self.data.close[0]
                pnl = round((sell_price - self.entry_price) / self.entry_price * 100, 2)
                self.sell(size=self.position.size)
                self.trades.append({
                    "entry_date": self.entry_date.isoformat(),
                    "exit_date": dt.isoformat(),
                    "entry_price": round(self.entry_price, 2),
                    "exit_price": round(sell_price, 2),
                    "pnl_pct": pnl,
                    "reason": exit_reason,
                    "size": self.position.size,
                })
                self.entry_price = None
                self.entry_date = None


class MACDStrategy(bt.Strategy):
    params = dict(
        fast_period=12,
        slow_period=26,
        signal_period=9,
        stop_loss_pct=0.08,
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period,
        )
        self.entry_price = None
        self.entry_date = None
        self.trades = []
        self.portfolio_values = []

    def next(self):
        dt = self.data.datetime.date(0)
        val = self.broker.getvalue()
        self.portfolio_values.append({
            "date": dt.isoformat(),
            "value": round(val, 2),
        })

        if not self.position:
            if self.macd.macd[0] > self.macd.signal[0] and self.macd.macd[-1] <= self.macd.signal[-1]:
                size = int((self.broker.getcash() * 0.95) / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = self.data.close[0]
                    self.entry_date = dt
        else:
            exit_reason = None
            if self.macd.macd[0] < self.macd.signal[0] and self.macd.macd[-1] >= self.macd.signal[-1]:
                exit_reason = "macd_cross"
            elif self.data.close[0] < self.entry_price * (1 - self.p.stop_loss_pct):
                exit_reason = "stop_loss"

            if exit_reason:
                sell_price = self.data.close[0]
                pnl = round((sell_price - self.entry_price) / self.entry_price * 100, 2)
                self.sell(size=self.position.size)
                self.trades.append({
                    "entry_date": self.entry_date.isoformat(),
                    "exit_date": dt.isoformat(),
                    "entry_price": round(self.entry_price, 2),
                    "exit_price": round(sell_price, 2),
                    "pnl_pct": pnl,
                    "reason": exit_reason,
                    "size": self.position.size,
                })
                self.entry_price = None
                self.entry_date = None


class BollingerStrategy(bt.Strategy):
    params = dict(
        period=20,
        devfactor=2.0,
        stop_loss_pct=0.08,
    )

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor,
        )
        self.entry_price = None
        self.entry_date = None
        self.trades = []
        self.portfolio_values = []

    def next(self):
        dt = self.data.datetime.date(0)
        val = self.broker.getvalue()
        self.portfolio_values.append({
            "date": dt.isoformat(),
            "value": round(val, 2),
        })

        if not self.position:
            if self.data.close[0] < self.boll.lines.bot[0]:
                size = int((self.broker.getcash() * 0.95) / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
                    self.entry_price = self.data.close[0]
                    self.entry_date = dt
        else:
            exit_reason = None
            if self.data.close[0] > self.boll.lines.top[0]:
                exit_reason = "take_profit"
            elif self.data.close[0] < self.entry_price * (1 - self.p.stop_loss_pct):
                exit_reason = "stop_loss"

            if exit_reason:
                sell_price = self.data.close[0]
                pnl = round((sell_price - self.entry_price) / self.entry_price * 100, 2)
                self.sell(size=self.position.size)
                self.trades.append({
                    "entry_date": self.entry_date.isoformat(),
                    "exit_date": dt.isoformat(),
                    "entry_price": round(self.entry_price, 2),
                    "exit_price": round(sell_price, 2),
                    "pnl_pct": pnl,
                    "reason": exit_reason,
                    "size": self.position.size,
                })
                self.entry_price = None
                self.entry_date = None


STRATEGY_MAP = {
    "dual_ma": DualMAStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
}


def get_kline_dataframe(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    db = get_db()
    klines = list(db.stock_kline.find({
        "code": code,
        "frequency": 9,
        "date": {"$gte": f"{start_date} 15:00", "$lte": f"{end_day} 15:00"} if False else {"$gte": f"{start_date} 15:00", "$lte": f"{end_date} 15:00"},
    }).sort("date", 1))

    if not klines or len(klines) < 30:
        return None

    rows = []
    for k in klines:
        rows.append({
            "datetime": pd.Timestamp(k["date"][:10]),
            "open": float(k["open"]),
            "high": float(k["high"]),
            "low": float(k["low"]),
            "close": float(k["close"]),
            "volume": float(k["volume"]),
        })

    df = pd.DataFrame(rows)
    df.set_index("datetime", inplace=True)
    return df


def run_backtest(
    strategy_name: str = "dual_ma",
    codes: List[str] = None,
    start_date: str = None,
    end_date: str = None,
    initial_cash: float = 100000,
    commission: float = 0.001,
    params: Dict = None,
) -> Dict[str, Any]:

    strategy_cls = STRATEGY_MAP.get(strategy_name)
    if not strategy_cls:
        return {"error": f"unknown strategy: {strategy_name}"}

    if not codes:
        db = get_db()
        codes = db.stock_kline.distinct("code", {"frequency": 9})

    if not start_date:
        start_date = (datetime.now() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    all_trades = []
    all_values = []
    processed = 0
    skipped = 0

    for code in codes:
        df = get_kline_dataframe(code, start_date, end_date)
        if df is None:
            skipped += 1
            continue

        cerebro = bt.Cerebro()
        cerebro.addstrategy(strategy_cls, **(params or {}))
        cerebro.adddata(bt.feeds.PandasData(dataname=df))
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=commission)
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        try:
            results = cerebro.run()
            strat = results[0]

            for t in strat.trades:
                t["code"] = code
            all_trades.extend(strat.trades)
            all_values.extend(strat.portfolio_values)
            processed += 1
        except Exception:
            skipped += 1
            continue

    if not all_trades:
        return {"strategy": strategy_name, "trades": 0, "processed": processed, "skipped": skipped}

    pnls = [t["pnl_pct"] for t in all_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = round(len(wins) / len(pnls) * 100, 1) if pnls else 0
    avg_win = round(sum(wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(losses) / len(losses), 2) if losses else 0
    profit_factor = round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else 99
    total_return = round(sum(pnls), 2)

    import statistics
    sharpe = round(statistics.mean(pnls) / statistics.stdev(pnls) * (252 ** 0.5), 2) if len(pnls) > 1 and statistics.stdev(pnls) > 0 else 0

    stopped = sum(1 for t in all_trades if t.get("reason") == "stop_loss")
    death_cross = sum(1 for t in all_trades if t.get("reason") == "death_cross")
    take_profit = sum(1 for t in all_trades if t.get("reason") == "take_profit")

    peak = 0
    max_dd = 0
    for v in all_values:
        if v["value"] > peak:
            peak = v["value"]
        dd = (peak - v["value"]) / peak * 100 if peak else 0
        if dd > max_dd:
            max_dd = dd

    return {
        "strategy": strategy_name,
        "trades": len(all_trades),
        "processed": processed,
        "skipped": skipped,
        "win_rate": win_rate,
        "avg_return": round(sum(pnls) / len(pnls), 2),
        "total_return": total_return,
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "sharpe": sharpe,
        "max_drawdown": round(max_dd, 2),
        "stopped_out": stopped,
        "death_cross": death_cross,
        "take_profit": take_profit,
        "initial_cash": initial_cash,
        "commission": commission,
        "examples": all_trades[:10],
        "equity_curve": all_values[-100:],
    }
