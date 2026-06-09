import backtrader as bt
import pandas as pd
import logging
import random
from datetime import datetime
from typing import Dict, Any, List
from database import get_db


_name_map_cache = None

def _load_name_map(force=False):
    global _name_map_cache
    if _name_map_cache is not None and not force:
        return _name_map_cache
    db = get_db()
    _name_map_cache = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        code = s.get("stock_code", "").split(".")[-1]
        if code:
            _name_map_cache[code] = s.get("stock_name", "")
    return _name_map_cache


def sample_market_stocks(n: int = 500, seed: int = None) -> List[str]:
    """从全市场抽样 n 只股票（排除ST、300、301、688），和实盘完全一致"""
    db = get_db()

    all_codes = db.stock_kline.distinct("code", {"frequency": 9})
    name_map = _load_name_map()

    filtered = [c for c in all_codes
                if name_map.get(c)  # 在 sector_stocks 没名字的（ETF/指数）跳过
                and not name_map.get(c, "").startswith(("ST", "*ST"))
                and not c.startswith(("300", "301", "688"))]

    pipeline = [
        {"$match": {"code": {"$in": filtered}, "frequency": 9}},
        {"$group": {"_id": "$code", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 20}}},
    ]
    result = list(db.stock_kline.aggregate(pipeline, allowDiskUse=True))
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(result)
    else:
        random.shuffle(result)
    valid_codes = [d["_id"] for d in result[:n]] if n > 0 else [d["_id"] for d in result]

    return valid_codes


def _load_aligned_klines(codes, start, end):
    """加载多只股票K线并对齐到统一交易日历"""
    import time
    t0 = time.time()
    db = get_db()

    klines_raw = list(db.stock_kline.find(
        {"code": {"$in": codes}, "frequency": 9,
         "date": {"$gte": f"{start} 15:00", "$lte": f"{end} 15:00"}},
        {"code": 1, "date": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ).sort("date", 1))
    logging.info(f"[ALIGN] MongoDB 查询 {len(klines_raw)} 条记录, 耗时 {time.time()-t0:.1f}s")

    t1 = time.time()
    stock_data = {}
    for k in klines_raw:
        stock_data.setdefault(k["code"], []).append(k)

    result = {}
    for code, klines in stock_data.items():
        if len(klines) < 20:
            continue
        rows = []
        for k in klines:
            rows.append({
                "datetime": pd.Timestamp(k["date"][:10]),
                "open": float(k["open"]), "high": float(k["high"]),
                "low": float(k["low"]), "close": float(k["close"]),
                "volume": float(k["volume"]),
            })
        df = pd.DataFrame(rows).set_index("datetime").sort_index()
        df = df[~df.index.duplicated(keep='first')]
        result[code] = df
    logging.info(f"[ALIGN] DataFrame 构建 {len(result)} 只, 耗时 {time.time()-t1:.1f}s")

    if not result:
        return result

    t2 = time.time()
    all_dates = sorted(set(
        date for df in result.values() for date in df.index
    ))
    first_cal = all_dates[0].strftime("%Y-%m-%d") if all_dates else "none"
    last_cal = all_dates[-1].strftime("%Y-%m-%d") if all_dates else "none"
    logging.info(f"[ALIGN] 全日历 {len(all_dates)} 天 ({first_cal}~{last_cal}), "
                 f"耗时 {time.time()-t2:.1f}s")

    t3 = time.time()
    for code in list(result.keys()):
        df = result[code]

        stock_dates = [d for d in all_dates if d >= df.index[0]]
        if len(stock_dates) < 20:
            del result[code]
            continue

        df = df.reindex(stock_dates)
        df = df.ffill()
        result[code] = df

    logging.info(f"[ALIGN] 对齐完成, 有效股票 {len(result)} 只, 耗时 {time.time()-t3:.1f}s")
    return result


def _load_aligned_indicators(codes, start, end):
    """从 stock_indicators 加载预计算指标

    Returns:
        {code: {date_str: {ma5, ma10, ..., adx, amplitude}}}
    """
    db = get_db()
    raw = list(db.stock_indicators.find(
        {"code": {"$in": codes}, "date": {"$gte": start, "$lte": end}},
    ).sort("date", 1))

    result = {}
    for doc in raw:
        code = doc["code"]
        date_str = doc["date"]
        result.setdefault(code, {})[date_str] = {
            "ma5": doc.get("ma5"),
            "ma10": doc.get("ma10"),
            "ma20": doc.get("ma20"),
            "ma60": doc.get("ma60"),
            "ma5_vol": doc.get("ma5_vol"),
            "high20": doc.get("high20"),
            "low20": doc.get("low20"),
            "rsi": doc.get("rsi"),
            "atr": doc.get("atr"),
            "adx": doc.get("adx"),
            "amplitude": doc.get("amplitude"),
        }

    return result


class PortfolioRuleStrategy(bt.Strategy):
    """组合策略：单Cerebro + 共享资金池 + 每天全市场选股"""

    params = dict(
        stock_codes=None, name_map=None, custom_rules=None,
        max_hold_days=60, cooldown_days=3, stop_loss_pct=0.08,
        max_positions=5, start_date_str=None,
        task_id=None, bars_total=0, precomputed_indicators=None,
    )

    def __init__(self):
        from bin.rule_engine import StockRuleEngine

        self.codes = list(self.p.stock_codes) if self.p.stock_codes else []
        self.name_map = self.p.name_map or {}

        if self.p.custom_rules is not None:
            self.rules = self.p.custom_rules
        else:
            db = get_db()
            self.rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))

        self.engine = StockRuleEngine(self.rules) if self.rules else None

        self.precomputed = self.p.precomputed_indicators or {}
        if not self.precomputed:
            logging.warning("[BACKTEST] 无预计算指标数据，回测将使用默认值")

        raw = self.p.start_date_str
        self.start_date = pd.Timestamp(raw).date() if raw else None
        self.entry_prices = {}
        self.entry_dates = {}
        self.last_exit_dates = {}
        self.trade_log = []

        self._bar_count = 0
        self._bars_total = self.p.bars_total or 0
        self._next_progress_pct = 5
        self._code_index = {code: i for i, code in enumerate(self.codes)}

    def _ctx(self, code, has_pos, cost, buy_date, today):
        from bin.rule_engine import StockRuleEngine
        d = self.datas[self._code_index[code]]

        date_str = d.datetime.date(0).isoformat()
        stock_ind = self.precomputed.get(code, {}).get(date_str, {})

        last_close = d.close[-1] if len(d) > 1 else d.close[0]
        amplitude = stock_ind.get("amplitude",
                                  (d.high[0] - d.low[0]) / last_close if last_close > 0 else 0)

        return StockRuleEngine.build_context({
            "close": d.close[0], "volume": d.volume[0],
            "ma5": stock_ind.get("ma5", d.close[0]),
            "ma10": stock_ind.get("ma10", d.close[0]),
            "ma20": stock_ind.get("ma20", d.close[0]),
            "ma60": stock_ind.get("ma60", d.close[0]),
            "ma5_vol": stock_ind.get("ma5_vol", d.volume[0]),
            "last_close": last_close,
            "high": stock_ind.get("high20", d.high[0]),
            "low": stock_ind.get("low20", d.low[0]),
            "open": d.open[0], "name": self.name_map.get(code, ""),
            "rsi": stock_ind.get("rsi", 50),
            "atr": stock_ind.get("atr", 0),
            "adx": stock_ind.get("adx", 25),
            "amplitude": amplitude,
        }, {"has_pos": has_pos, "cost": cost, "buy_date": buy_date, "today": today})

    def next(self):
        if not self.engine:
            return
        dt = self.datas[0].datetime.date(0)
        if self.start_date and dt < self.start_date:
            return

        self._bar_count += 1
        pct = int(self._bar_count * 100 / self._bars_total) if self._bars_total else 0
        if pct >= self._next_progress_pct and self._next_progress_pct <= 100 and self.p.task_id:
            _update_progress(self.p.task_id, self._bar_count, self._bars_total,
                             f"回测中... [{pct}%]", f"第 {self._bar_count}/{self._bars_total} 个交易日")
            self._next_progress_pct += 5

        try:
            # ==== 第一步：卖出 ====
            for code in list(self.entry_prices.keys()):
                d = self.datas[self._code_index[code]]
                hold_days = (dt - self.entry_dates[code]).days

                if hold_days < 1:
                    continue

                ctx = self._ctx(code, True, self.entry_prices[code], self.entry_dates[code], dt)
                risk, sell_score, _, triggered = self.engine.run(ctx)

                if risk and len(self.trade_log) < 20:
                    risk_rules = [r["name"] for r in triggered if r["type"] == "risk"]
                    logging.info(f"[SELL_DEBUG] {code} risk={risk} sell_scr={sell_score:.1f} "
                                 f"close={d.close[0]:.2f} cost={self.entry_prices[code]:.2f} "
                                 f"stop_loss={self.entry_prices[code]*(1-self.p.stop_loss_pct):.2f} "
                                 f"triggered={risk_rules}")

                reason = None
                if risk:
                    reason = "risk"
                elif d.close[0] < self.entry_prices[code] * (1 - self.p.stop_loss_pct):
                    reason = "stop_loss"
                elif sell_score > 0:
                    reason = "sell"
                elif hold_days >= self.p.max_hold_days:
                    reason = "timeout"

                if reason:
                    entry_price = self.entry_prices[code]
                    if entry_price == 0:
                        continue
                    pnl = round((d.close[0] - entry_price) / entry_price * 100, 2)
                    self.trade_log.append({
                        "code": code, "name": self.name_map.get(code, ""),
                        "entry_date": self.entry_dates[code].isoformat(),
                        "exit_date": dt.isoformat(),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(d.close[0], 2),
                        "pnl_pct": pnl,
                        "hold_days": hold_days,
                        "reason": reason,
                        "triggered_rules": [r["name"] for r in (triggered or [])],
                    })
                    self.sell(data=d)
                    del self.entry_prices[code]
                    del self.entry_dates[code]
                    self.last_exit_dates[code] = dt

            # ==== 第二步：买入 ====
            if len(self.entry_prices) >= self.p.max_positions:
                return

            buy_candidates = []
            for i, code in enumerate(self.codes):
                if code in self.entry_prices:
                    continue
                if code in self.last_exit_dates and (dt - self.last_exit_dates[code]).days < self.p.cooldown_days:
                    continue
                if self.datas[self._code_index[code]].close[0] <= 0:
                    continue

                ctx = self._ctx(code, False, 0, None, dt)
                _, _, buy_score, _ = self.engine.run(ctx)
                if buy_score > 0:
                    buy_candidates.append((buy_score, code))

            if not buy_candidates:
                return

            buy_candidates.sort(key=lambda x: x[0], reverse=True)
            available_cash = self.broker.getcash()
            current_positions = len(self.entry_prices)

            for buy_score, code in buy_candidates:
                if current_positions >= self.p.max_positions:
                    break

                d = self.datas[self._code_index[code]]
                price = d.close[0]
                if price <= 0:
                    continue

                remaining_slots = self.p.max_positions - current_positions
                if remaining_slots <= 0:
                    break
                position_cash = available_cash / remaining_slots
                if available_cash <= 0 or position_cash <= 0:
                    break

                size = int(position_cash / price)
                if size <= 0:
                    continue

                self.buy(data=d, size=size)
                self.entry_prices[code] = price
                self.entry_dates[code] = dt
                current_positions += 1
                available_cash -= size * price

        except Exception as e:
            import traceback
            logging.error(f"[NEXT] {dt} error: {e}\n{traceback.format_exc()}")


def _update_progress(task_id, current, total, status, detail="", result=None):
    try:
        doc = {"current": current, "total": total, "status": status, "detail": detail, "updated_at": datetime.now()}
        if result is not None:
            doc["result"] = result
        db = get_db()
        db.backtest_progress.update_one(
            {"_id": task_id},
            {"$set": doc},
            upsert=True,
        )
    except Exception as e:
        logging.error(f"进度更新失败: {e}")


def run_backtest(strategy_name="portfolio_rule_engine", codes=None, start_date=None, end_date=None,
                 initial_cash=100000, commission=0.001, custom_rules=None, max_stocks=0,
                 celery_task=None, task_id=None, max_positions=5):

    if not start_date:
        start_date = (datetime.now() - pd.Timedelta(days=360)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    warmup_days = 60
    load_start = (pd.Timestamp(start_date) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")

    db = get_db()

    if not codes:
        if max_stocks > 0:
            codes = sample_market_stocks(max_stocks, seed=42)
            logging.info(f"[BACKTEST] 从指数成分股中抽样 {len(codes)} 只")
        else:
            codes = db.stock_kline.distinct("code", {"frequency": 9})

    name_map = _load_name_map()

    filtered = [c for c in codes
                if name_map.get(c)
                and not name_map.get(c, "").startswith(("ST", "*ST"))
                and not c.startswith(("300", "301", "688"))]

    logging.info(f"[BACKTEST] {start_date}~{end_date} cash={initial_cash} codes={len(filtered)} max_positions={max_positions} (向前取{warmup_days}天用于指标预热)")

    if task_id:
        _update_progress(task_id, 0, len(filtered), "加载K线数据...", f"共 {len(filtered)} 只股票")
    logging.info(f"[BACKTEST] 批量加载K线数据...")

    stock_dfs = _load_aligned_klines(filtered, load_start, end_date)

    indicators = _load_aligned_indicators(filtered, load_start, end_date)
    if task_id:
        total_ind = sum(len(v) for v in indicators.values())
        logging.info(f"[BACKTEST] 预计算指标已加载: {len(indicators)} 只股票, {total_ind} 条记录")

    if task_id:
        loaded = sum(len(df) for df in stock_dfs.values())
        _update_progress(task_id, 0, len(stock_dfs), "K线加载完成", f"{len(stock_dfs)} 只股票, {loaded} 条K线")

    start_ts = pd.Timestamp(start_date)
    codes_with_data = [code for code, df in stock_dfs.items() if df.index[0] <= start_ts]
    skipped_new = len(stock_dfs) - len(codes_with_data)
    if skipped_new:
        logging.info(f"[BACKTEST] 剔除{skipped_new}只上市日期晚于{start_date}的股票，保留{len(codes_with_data)}只")
    logging.info(f"[BACKTEST] 加载完成，有效股票 {len(codes_with_data)} 只")

    if not codes_with_data:
        if task_id:
            _update_progress(task_id, 0, 0, "无有效股票", "所有股票因数据不足被过滤")
        return {"strategy": strategy_name, "trades": 0, "processed": 0, "skipped": len(filtered)}

    if task_id:
        _update_progress(task_id, 0, len(codes_with_data), "运行组合回测...", f"加载 {len(codes_with_data)} 只股票数据")

    # 计算回测期内 next() 实际会被调用的交易日数
    # backtrader 从最晚有数据的股票才开始，所以取 codes_with_data 中最晚起始日
    end_ts = pd.Timestamp(end_date)
    all_dates = set()
    for df in stock_dfs.values():
        all_dates.update(df.index)
    if codes_with_data:
        latest_start = max(stock_dfs[code].index[0] for code in codes_with_data)
        bars_total = sum(1 for d in all_dates if latest_start <= d <= end_ts)
        logging.info(f"[BACKTEST] 交易日: {bars_total} 天 (从 {latest_start.date()} 开始, 最晚上市股)")
    else:
        bars_total = 0

    if task_id:
        _update_progress(task_id, 0, bars_total, "运行组合回测...",
                         f"{len(codes_with_data)} 只股票, {bars_total} 个交易日")

    cerebro = bt.Cerebro()
    cerebro.addstrategy(PortfolioRuleStrategy,
                        stock_codes=codes_with_data,
                        name_map=name_map,
                        custom_rules=custom_rules,
                        max_positions=max_positions,
                        start_date_str=start_date,
                        task_id=task_id,
                        bars_total=bars_total,
                        precomputed_indicators=indicators)

    for code in codes_with_data:
        cerebro.adddata(bt.feeds.PandasData(dataname=stock_dfs[code]))

    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    logging.disable(logging.INFO)
    try:
        strat = cerebro.run()[0]
    except Exception as e:
        logging.disable(logging.NOTSET)
        logging.error(f"[BACKTEST] 回测执行失败: {e}")
        if task_id:
            _update_progress(task_id, 0, 0, "回测失败", str(e))
        return {"strategy": strategy_name, "trades": 0, "processed": 0,
                "skipped": len(filtered), "error": str(e)}
    logging.disable(logging.NOTSET)

    all_trades = strat.trade_log
    end_value = cerebro.broker.getvalue()
    start_value = initial_cash
    portfolio_return = round((end_value - start_value) / start_value * 100, 2)

    logging.info(f"[BACKTEST] 组合: {start_value} -> {end_value:.0f} ({portfolio_return}%) trades={len(all_trades)}")

    if not all_trades:
        result = {
            "strategy": strategy_name, "trades": 0,
            "processed": len(codes_with_data), "skipped": len(filtered) - len(codes_with_data),
            "portfolio_return": portfolio_return,
        }
        if task_id:
            _update_progress(task_id, bars_total, bars_total, "回测完成（无交易）",
                             "没有触发买入信号", result=result)
        return result

    pnls = [t["pnl_pct"] for t in all_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    import statistics

    unique_codes = len(set(t["code"] for t in all_trades))

    exit_stats = {}
    for t in all_trades:
        exit_stats[t["reason"]] = exit_stats.get(t["reason"], 0) + 1

    sharpe = round(statistics.mean(pnls) / statistics.stdev(pnls) * (252 ** 0.5), 2) \
        if len(pnls) > 1 and statistics.stdev(pnls) > 0 else 0

    result = {
        "strategy": strategy_name, "trades": len(all_trades),
        "processed": len(codes_with_data),
        "skipped": len(filtered) - len(codes_with_data),
        "unique_stocks": unique_codes,
        "portfolio_return": portfolio_return,
        "win_rate": round(len(wins) / len(pnls) * 100, 1),
        "avg_return": round(sum(pnls) / len(pnls), 2),
        "total_return": round(sum(pnls), 2),
        "best": round(max(pnls), 2), "worst": round(min(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else float('inf'),
        "sharpe": sharpe,
        "exit_stats": exit_stats,
        "trades_list": all_trades,
        "examples_best": sorted(all_trades, key=lambda t: t["pnl_pct"], reverse=True)[:10],
        "examples_worst": sorted(all_trades, key=lambda t: t["pnl_pct"])[:10],
    }

    logging.info(f"[RESULT] 组合收益={portfolio_return}% trades={len(all_trades)} win_rate={result['win_rate']}% sharpe={sharpe}")
    for t in all_trades:
        logging.info(f"[TRADE] {t['code']} {t.get('name','')} buy={t['entry_date']}@{t['entry_price']} sell={t['exit_date']}@{t['exit_price']} pnl={t['pnl_pct']}% hold={t['hold_days']}d reason={t['reason']}")

    if task_id:
        _update_progress(task_id, bars_total, bars_total, "回测完成",
                         f"交易 {len(all_trades)} 笔", result=result)

    return result
