import pandas as pd
import logging
import random
from datetime import datetime, timedelta
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
    db = get_db()

    codes = db.stock_kline.distinct("code", {"frequency": 9})
    name_map = _load_name_map()

    filtered = [c for c in codes
                if name_map.get(c)
                and not name_map.get(c, "").startswith(("ST", "*ST"))
                and not c.startswith(("300", "301", "688"))]

    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(filtered)
    else:
        random.shuffle(filtered)

    return filtered[:n] if n > 0 else filtered


def _load_data(codes, start, end):
    """从 stock_indicators 加载所有回测所需数据（OHLCV + 指标）

    同时加载 stock_indicators 中的 code+date 范围数据，过滤数据不足的股票。
    返回统一的 {code: {date_str: {open, close, high, low, volume, ...indicator_fields}}}

    注意: 需要 stock_indicators 中存储 open/close/high/low/volume 字段。
    如果旧数据缺失 high/low，以 close 兜底。
    """
    import time
    t0 = time.time()
    db = get_db()

    raw = list(db.stock_indicators.find(
        {"code": {"$in": codes}, "date": {"$gte": start, "$lte": end}},
    ).sort("date", 1))

    logging.info(f"[LOAD] stock_indicators 查询 {len(raw)} 条, 耗时 {time.time()-t0:.1f}s")

    t1 = time.time()
    result = {}
    for doc in raw:
        code = doc["code"]
        close_val = doc.get("close", 0)
        result.setdefault(code, {})[doc["date"]] = {
            "open": doc.get("open", close_val),
            "close": close_val,
            "high": doc.get("high", close_val),
            "low": doc.get("low", close_val),
            "volume": doc.get("volume", 0),
            "last_close": doc.get("last_close", close_val),
            "ma5": doc.get("ma5", close_val),
            "ma10": doc.get("ma10", close_val),
            "ma20": doc.get("ma20", close_val),
            "ma60": doc.get("ma60", close_val),
            "ma5_vol": doc.get("ma5_vol", 0),
            "high20": doc.get("high20", close_val),
            "low20": doc.get("low20", close_val),
            "rsi": doc.get("rsi", 50),
            "atr": doc.get("atr", 0),
            "adx": doc.get("adx", 25),
            "amplitude": doc.get("amplitude", 0),
        }

    result = {c: d for c, d in result.items() if len(d) >= 20}
    logging.info(f"[LOAD] 解析完成 {len(result)} 只, 耗时 {time.time()-t1:.1f}s")
    return result


def _get_dates_sorted(data):
    """获取所有股票统一的交易日列表（按日期排序）"""
    all_dates = set()
    for code_dates in data.values():
        all_dates.update(code_dates.keys())
    return sorted(all_dates)


def _build_ctx(indicators, code, name, has_pos, cost, buy_date, today):
    """构建规则引擎上下文"""
    from bin.rule_engine import StockRuleEngine

    d = indicators
    if not d:
        return None

    last_close = d.get("last_close", d.get("close", 0))

    return StockRuleEngine.build_context({
        "close": d.get("close", 0),
        "volume": d.get("volume", 0),
        "ma5": d.get("ma5", d.get("close", 0)),
        "ma10": d.get("ma10", d.get("close", 0)),
        "ma20": d.get("ma20", d.get("close", 0)),
        "ma60": d.get("ma60", d.get("close", 0)),
        "ma5_vol": d.get("ma5_vol", d.get("volume", 0)),
        "last_close": last_close,
        "high": d.get("high20", d.get("high", d.get("close", 0))),
        "low": d.get("low20", d.get("low", d.get("close", 0))),
        "open": d.get("open", d.get("close", 0)),
        "name": name,
        "rsi": d.get("rsi", 50),
        "atr": d.get("atr", 0),
        "adx": d.get("adx", 25),
        "amplitude": d.get("amplitude", 0),
    }, {"has_pos": has_pos, "cost": cost, "buy_date": buy_date, "today": today})


def run_backtest(strategy_name="portfolio_rule_engine", codes=None, start_date=None, end_date=None,
                 initial_cash=100000, commission=0.001, custom_rules=None, max_stocks=0,
                 celery_task=None, task_id=None, max_positions=5,
                 max_hold_days=60, cooldown_days=1):

    if not start_date:
        start_date = (datetime.now() - timedelta(days=360)).strftime("%Y-%m-%d")
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
        _update_progress(task_id, 0, len(filtered), "加载指标数据...", f"共 {len(filtered)} 只股票")

    logging.info(f"[BACKTEST] 从 stock_indicators 加载数据...")
    data = _load_data(filtered, load_start, end_date)
    dates = _get_dates_sorted(data)

    total_dates = sum(1 for d in dates if load_start <= d <= end_date)
    logging.info(f"[BACKTEST] 交易日: {total_dates} 天, 股票: {len(data)} 只")

    if not data:
        if task_id:
            _update_progress(task_id, 0, 0, "无有效数据", "所有股票指标数据不足")
        return {"strategy": strategy_name, "trades": 0, "processed": 0, "skipped": len(filtered)}

    # --- 加载规则引擎 ---
    from bin.rule_engine import StockRuleEngine

    if custom_rules is not None:
        rules = custom_rules
    else:
        rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))

    engine = StockRuleEngine(rules) if rules else None
    if not engine:
        logging.warning("[BACKTEST] 无可用规则")
        return {"strategy": strategy_name, "trades": 0, "processed": len(data), "skipped": 0}

    logging.info(f"[BACKTEST] 规则数: {len(rules)} 条")

    # --- 回测状态 ---
    cash = initial_cash
    positions = {}  # code -> {cost, buy_date, shares, cost_total}
    last_exit_dates = {}
    trade_log = []
    bar_count = 0
    total_bars = total_dates
    next_progress_pct = 5

    start_ts = pd.Timestamp(start_date).strftime("%Y-%m-%d")

    logging.info(f"[BACKTEST] 开始回测, 共 {total_bars} 天")

    for date_str in dates:
        bar_count += 1

        # 预热期不交易
        if date_str < start_ts:
            continue

        if task_id and bar_count > 0 and total_bars > 0:
            pct = int(bar_count * 100 / total_bars)
            if pct >= next_progress_pct and next_progress_pct <= 100:
                _update_progress(task_id, bar_count, total_bars,
                                 f"回测中... [{pct}%]", f"第 {bar_count}/{total_bars} 个交易日")
                next_progress_pct += 5

        today = pd.Timestamp(date_str).date()

        # ==== 第一步：卖出 ====
        for code in list(positions.keys()):
            ind = data.get(code, {}).get(date_str)
            if not ind:
                continue

            hold_days = (today - positions[code]["buy_date"]).days
            if hold_days < 1:
                continue

            ctx = _build_ctx(ind, code, name_map.get(code, ""),
                             True, positions[code]["cost"],
                             positions[code]["buy_date"], today)
            if not ctx:
                continue

            risk, sell_score, _, triggered = engine.run(ctx)
            close_price = ind["close"]

            reason = None
            if risk:
                reason = "risk"
            elif sell_score > 0:
                reason = "sell"
            elif hold_days >= max_hold_days:
                reason = "timeout"

            if reason:
                entry_price = positions[code]["cost"]
                if entry_price <= 0:
                    continue
                pnl = round((close_price - entry_price) / entry_price * 100, 2)

                # 计算佣金（双边）
                total_cost = positions[code]["cost_total"]
                total_sell = positions[code]["shares"] * close_price
                trade_commission = total_cost * commission + total_sell * commission
                cash += total_sell - trade_commission

                trade_log.append({
                    "code": code,
                    "name": name_map.get(code, ""),
                    "entry_date": positions[code]["buy_date"].isoformat(),
                    "exit_date": today.isoformat(),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(close_price, 2),
                    "pnl_pct": pnl,
                    "hold_days": hold_days,
                    "reason": reason,
                    "triggered_rules": [r["name"] for r in (triggered or [])],
                })

                last_exit_dates[code] = today
                del positions[code]

        # ==== 第二步：买入 ====
        if len(positions) >= max_positions:
            continue

        buy_candidates = []
        for code in data:
            if code in positions:
                continue
            if code in last_exit_dates and (today - last_exit_dates[code]).days < cooldown_days:
                continue

            ind = data[code].get(date_str)
            if not ind or ind.get("close", 0) <= 0:
                continue

            ctx = _build_ctx(ind, code, name_map.get(code, ""),
                             False, 0, None, today)
            if not ctx:
                continue

            _, _, buy_score, _ = engine.run(ctx)
            if buy_score > 0:
                buy_candidates.append((buy_score, code))

        if not buy_candidates:
            continue

        buy_candidates.sort(key=lambda x: x[0], reverse=True)
        remaining_slots = max_positions - len(positions)

        for _, code in buy_candidates:
            if len(positions) >= max_positions:
                break

            ind = data[code][date_str]
            price = ind["close"]
            if price <= 0:
                continue

            position_cash = cash / remaining_slots if remaining_slots > 0 else 0
            if position_cash <= 0:
                break

            shares = int(position_cash / price)
            if shares < 100:
                continue

            cost_total = shares * price
            trade_commission = cost_total * commission
            if cash < cost_total + trade_commission:
                continue

            cash -= cost_total + trade_commission
            positions[code] = {
                "cost": price,
                "buy_date": today,
                "shares": shares,
                "cost_total": cost_total,
            }
            remaining_slots -= 1

    # ==== 回测结束：强制平仓 ====
    end_today = pd.Timestamp(end_date).date()
    for code, pos in list(positions.items()):
        last_ind = None
        for d in sorted(data.get(code, {}).keys(), reverse=True):
            if d <= end_date:
                last_ind = data[code][d]
                break
        if not last_ind:
            continue

        close_price = last_ind["close"]
        entry_price = pos["cost"]
        if entry_price <= 0:
            continue
        pnl = round((close_price - entry_price) / entry_price * 100, 2)

        total_sell = pos["shares"] * close_price
        trade_commission = total_sell * commission
        cash += total_sell - trade_commission

        trade_log.append({
            "code": code,
            "name": name_map.get(code, ""),
            "entry_date": pos["buy_date"].isoformat(),
            "exit_date": end_today.isoformat(),
            "entry_price": round(entry_price, 2),
            "exit_price": round(close_price, 2),
            "pnl_pct": pnl,
            "hold_days": (end_today - pos["buy_date"]).days,
            "reason": "timeout",
            "triggered_rules": [],
        })
        del positions[code]

    # ==== 统计 ====
    all_trades = trade_log
    if not all_trades:
        logging.info(f"[BACKTEST] 未产生任何交易")
        return {
            "strategy": strategy_name, "trades": 0,
            "processed": len(data), "skipped": 0,
            "rules": [r.get("name", "") for r in rules],
        }

    import statistics

    pnls = [t["pnl_pct"] for t in all_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    portfolio_return = round((cash - initial_cash) / initial_cash * 100, 2)
    unique_codes = len(set(t["code"] for t in all_trades))

    exit_stats = {}
    for t in all_trades:
        exit_stats[t["reason"]] = exit_stats.get(t["reason"], 0) + 1

    sharpe = round(statistics.mean(pnls) / statistics.stdev(pnls) * (252 ** 0.5), 2) \
        if len(pnls) > 1 and statistics.stdev(pnls) > 0 else 0

    result = {
        "strategy": strategy_name,
        "trades": len(all_trades),
        "processed": len(data),
        "skipped": len(filtered) - len(data) if len(filtered) > len(data) else 0,
        "unique_stocks": unique_codes,
        "portfolio_return": portfolio_return,
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
        "avg_return": round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "total_return": round(sum(pnls), 2),
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "profit_factor": round(abs(sum(wins) / sum(losses)), 2) if losses and sum(losses) != 0 else float('inf'),
        "sharpe": sharpe,
        "exit_stats": exit_stats,
        "trades_list": all_trades,
        "rules": [r.get("name", "") for r in rules],
    }

    logging.info(f"[RESULT] 组合收益={portfolio_return}% trades={len(all_trades)} win_rate={result['win_rate']}% sharpe={sharpe}")

    if task_id:
        _update_progress(task_id, total_bars, total_bars, "回测完成",
                         f"交易 {len(all_trades)} 笔", result=result)

    return result


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