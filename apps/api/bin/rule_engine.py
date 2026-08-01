# -*- coding: utf-8 -*-
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
import time
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from systems.logs import Log

logger = logging.getLogger(__name__)
from systems.single import ScriptSingle
from systems.sys import home

from services.notification_service import send_dingtalk_message
from services.scoring.oversold_bounce import oversold_bounce_score, score_detail


# Mongo query retry count (spec REQ-003 exception table: retry 3 times)
MONGO_RETRY = 3
# Failure ratio threshold (spec REQ-003 exception table: >=10% aborts)
FAILURE_ABORT_RATIO = 0.10


def _mongo_find_with_retry(db, collection, query, projection=None, sort=None):
    """MongoDB query with retry. Returns list. Raises after MONGO_RETRY failures."""
    last_exc = None
    for attempt in range(MONGO_RETRY):
        try:
            cur = db[collection].find(query, projection) if projection else db[collection].find(query)
            if sort:
                cur = cur.sort(*sort) if isinstance(sort, tuple) else cur.sort(sort)
            return list(cur)
        except Exception as e:
            last_exc = e
            logging.warning(f"[RULE_ENGINE] Mongo {collection} attempt {attempt+1}/{MONGO_RETRY} failed: {e}")
            if attempt < MONGO_RETRY - 1:
                time.sleep(5)
    raise last_exc if last_exc else RuntimeError("mongo query failed")


class StockRuleEngine:
    def __init__(self, rules: List[Dict]):
        self.rules = sorted(rules, key=lambda r: r.get("priority", 99))
        self._compiled = []
        for rule in self.rules:
            try:
                code = compile(rule["condition"], "<rule>", "eval")
                self._compiled.append((rule, code))
            except SyntaxError as e:
                logging.error(f"规则编译失败: {e}, 规则: {rule.get('name', '')}")
                self._compiled.append((rule, None))

    def run(self, ctx: dict) -> tuple:
        risk_triggered = False
        sell_score = 0.0
        buy_score = 0.0
        triggered_rules = []

        for rule, code in self._compiled:
            if not rule.get("enabled", True) or code is None:
                continue
            try:
                ok = bool(eval(code, {"__builtins__": {}}, ctx))
            except Exception as e:
                logging.error(f"规则执行错误: {e}, 规则: {rule.get('name', '')}")
                continue
            if ok:
                triggered_rules.append(rule)
                if rule["type"] == "risk":
                    risk_triggered = True
                elif rule["type"] == "sell":
                    sell_score += rule.get("weight", 0)
                elif rule["type"] == "buy":
                    buy_score += rule.get("weight", 0)

        return risk_triggered, sell_score, buy_score, triggered_rules

    @staticmethod
    def build_context(stock_data: dict, position: Optional[dict]) -> dict:
        if position is None:
            position = {}

        today = position.get("today", datetime.now().date())
        today_num = today.toordinal() if isinstance(today, date) else datetime.now().date().toordinal()

        buy_date = position.get("buy_date")
        buy_date_num = buy_date.toordinal() if isinstance(buy_date, date) else today_num

        ctx = {
            "price": stock_data.get("close", 0),
            "vol": stock_data.get("volume", 0),
            "ma5": stock_data.get("ma5", 0),
            "ma10": stock_data.get("ma10", 0),
            "ma20": stock_data.get("ma20", 0),
            "ma60": stock_data.get("ma60", 0),
            "ma5_vol": stock_data.get("ma5_vol", 0),
            "last_close": stock_data.get("last_close", 0),
            "high": stock_data.get("high", 0),
            "low": stock_data.get("low", 0),
            "open": stock_data.get("open", 0),
            "rsi": stock_data.get("rsi", 0),
            "atr": stock_data.get("atr", 0),
            "adx": stock_data.get("adx", 0),
            "amplitude": stock_data.get("amplitude", 0),
            "has_pos": position.get("has_pos", False),
            "cost": position.get("cost", 0),
            "buy_date": buy_date_num,
            "today": today_num,
        }
        return ctx


def calc_sma(data, n):
    """简单移动平均"""
    if len(data) < n:
        logger.debug("calc_sma: need %d values, got %d, fallback to last value", n, len(data))
        return data[-1]
    return sum(data[-n:]) / n


def calc_rsi(prices, period=14):
    """RSI 相对强弱指标 (Wilder 平滑，与 backtrader 一致)"""
    if len(prices) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gain = diff if diff > 0 else 0
        loss = -diff if diff < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_atr(highs, lows, closes, period=14):
    """ATR 真实波动幅度 (Wilder 平滑，与 backtrader 一致)"""
    if len(closes) < 2:
        return (highs[-1] - lows[-1]) if (highs[-1] - lows[-1]) > 0 else 0
    trs = []
    for i in range(1, len(highs)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if len(trs) < period:
        return trs[-1] if trs else 0
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def calc_adx(highs, lows, closes, period=14):
    """ADX 平均趋向指数 (0~100)，Wilder's 平滑，与 backtrader 保持一致"""
    if len(closes) < period * 2:
        return 25

    trs, plus_dms, minus_dms = [], [], []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dms.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dms.append(down_move if down_move > up_move and down_move > 0 else 0)

    s_tr = sum(trs[:period]) / period
    s_pdm = sum(plus_dms[:period]) / period
    s_mdm = sum(minus_dms[:period]) / period

    dxs = []
    for i in range(period, len(trs)):
        s_tr = (s_tr * (period - 1) + trs[i]) / period
        s_pdm = (s_pdm * (period - 1) + plus_dms[i]) / period
        s_mdm = (s_mdm * (period - 1) + minus_dms[i]) / period
        pdi = s_pdm / s_tr * 100 if s_tr > 0 else 0
        mdi = s_mdm / s_tr * 100 if s_tr > 0 else 0
        if pdi + mdi == 0:
            continue
        dxs.append(abs(pdi - mdi) / (pdi + mdi) * 100)

    if len(dxs) < period:
        return round(dxs[-1], 1) if dxs else 25

    adx = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        adx = (adx * (period - 1) + dxs[i]) / period
    return round(adx, 1)


def load_stock_klines(db, codes, days=60):
    """批量加载K线数据 (含 Mongo 重试)"""
    now = datetime.now()
    start_str = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d") + " 23:59"
    klines_raw = _mongo_find_with_retry(
        db, "stock_kline",
        {"code": {"$in": codes}, "frequency": 9, "date": {"$gte": start_str, "$lte": end_str}},
        sort=("date", 1),
    )
    stock_klines = {}
    for k in klines_raw:
        stock_klines.setdefault(k["code"], []).append(k)
    return stock_klines


def build_stock_indicators(klines):
    """从K线数据计算技术指标，返回 stock_data 字典

    Note: high20 key uses 'high' field (20-day high) -> caller passes 'high' key for high20.
    """
    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]

    kline = klines[-1]
    cur_close = closes[-1]
    open_val = kline.get("open")
    if open_val is None:
        logger.warning("build_stock_indicators: missing 'open' in kline for code=%s", kline.get("code", "?"))
        open_val = 0
    prev_close = closes[-2] if len(closes) >= 2 else cur_close
    atr = calc_atr(highs, lows, closes)
    amplitude = (highs[-1] - lows[-1]) / prev_close if prev_close > 0 else 0

    return {
        "close": cur_close,
        "volume": volumes[-1],
        "ma5": calc_sma(closes, 5),
        "ma10": calc_sma(closes, 10),
        "ma20": calc_sma(closes, 20),
        "ma60": calc_sma(closes, 60),
        "ma5_vol": calc_sma(volumes, 5),
        "last_close": prev_close,
        "high": max(highs[-20:]),
        "low": min(lows[-20:]),
        "open": open_val,
        "rsi": calc_rsi(closes),
        "atr": atr,
        "adx": calc_adx(highs, lows, closes),
        "amplitude": amplitude,
    }, atr


def suggest_prices(stock_data, atr):
    """基于 ATR 动态计算建议买入/卖出价格"""
    close = stock_data["close"]
    atr_pct = atr / close if close > 0 else 0.03
    mult = max(0.3, min(3.0, 0.03 / atr_pct)) if atr_pct > 0 else 1.0
    buy_price = round(close - atr * mult, 2)
    sell_price = round(close + atr * mult, 2)
    stop_loss = round(close - 2 * atr * mult, 2)
    return buy_price, sell_price, stop_loss


def _load_all_market_stocks(db, exclude_codes: set):
    """全市场扫描非 ST 股票代码与名称映射 (使用 sector_stocks)"""
    name_map = {}
    for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
        code = s.get("stock_code", "").split(".")[-1]
        name = s.get("stock_name", "")
        if code:
            name_map[code] = name

    all_codes = db.stock_kline.distinct("code", {"frequency": 9})
    non_st = [c for c in all_codes
              if c not in exclude_codes
              and not name_map.get(c, "").startswith(("ST", "*ST"))
              and not c.startswith(("300", "301", "688"))]
    logging.info(f"[RULE_ENGINE] 全市场非ST股票: {len(non_st)} 只")
    return non_st, name_map


def run_rules_for_holdings():
    """从 MongoDB 获取持仓和 K 线数据，执行所有启用规则

    持仓 -> has_pos=True（评估卖出/风控）
    全市场 -> 排除ST -> has_pos=False（评估买入）
    买入信号按 oversold_bounce_score 排序，只推送最高分的那只
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from database import get_db
    from config.config import settings

    db = get_db()

    # 1. 读取所有启用的规则
    rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))
    if not rules:
        logging.info("没有启用的交易规则")
        return
    has_buy_rule = any(r["type"] == "buy" for r in rules)

    # 2. 构建持仓池（用于评估卖出/风控）
    holdings = list(db.holdings.find({}))
    holding_codes = set(h["code"] for h in holdings)
    holding_map = {h["code"]: h for h in holdings}
    logging.info(f"持仓数量: {len(holding_codes)}")

    # 3. 候选池：全市场扫描，不再做双均线预过滤 (spec REQ-003)
    stock_klines_all = {}
    name_map = {}
    if has_buy_rule:
        non_st_codes, name_map = _load_all_market_stocks(db, exclude_codes=holding_codes)
        try:
            stock_klines_all = load_stock_klines(db, non_st_codes)
        except Exception as e:
            logging.error(f"[RULE_ENGINE] 全市场K线加载失败: {e}")
            return
        logging.info(f"买入候选池: {len(non_st_codes)} 只（全市场，排除持仓/ST）")
    else:
        if holdings:
            stock_klines_all = load_stock_klines(db, list(holding_codes))
            for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
                code = s.get("stock_code", "").split(".")[-1]
                if code:
                    name_map[code] = s.get("stock_name", "")

    # 4. 合并所有需要扫描的股票代码
    all_codes = list(holding_codes)
    if has_buy_rule:
        all_codes = list(set(all_codes) | set(stock_klines_all.keys()))
    if not all_codes:
        logging.info("没有股票需要扫描")
        return

    # 5. 补充持仓股票的 K 线数据（如果没有加载过）
    missing_codes = [c for c in holding_codes if c not in stock_klines_all]
    if missing_codes:
        try:
            extra_klines = load_stock_klines(db, missing_codes)
            stock_klines_all.update(extra_klines)
        except Exception as e:
            logging.error(f"[RULE_ENGINE] 持仓K线补充加载失败: {e}")

    engine = StockRuleEngine(rules)
    buy_candidates = []
    sell_messages = []
    pending_alerts = []

    # 6. 执行规则扫描 (with 失败计数与 10% 阈值终止)
    total = len(all_codes)
    failed_count = 0
    for idx, code in enumerate(all_codes, 1):
        if idx % 200 == 0 or idx == 1 or idx == total:
            logging.info(f"[RULE_ENGINE] 扫描进度: {idx}/{total}")

        try:
            klines = stock_klines_all.get(code, [])
            if not klines or len(klines) < 20:
                continue

            stock_data, atr = build_stock_indicators(klines)
            stock_data["name"] = name_map.get(code, "")
            is_holding = code in holding_map

            today_str = datetime.now().strftime("%Y-%m-%d")

            if is_holding:
                # 持仓股票：只执行卖出/风控规则
                h = holding_map[code]
                position = {
                    "has_pos": True,
                    "cost": h.get("average_cost", 0),
                    "buy_date": h["created_at"].date() if isinstance(h.get("created_at"), datetime) else None,
                }
                ctx = engine.build_context(stock_data, position)
                risk, sell_sc, buy_sc, triggered = engine.run(ctx)

                if not triggered:
                    continue

                rule_ids = sorted(r["rule_id"] for r in triggered)
                dedup_key = f"{code}|{today_str}|{rule_ids}"

                if db.alert_log.find_one({"dedup_key": dedup_key}):
                    logging.info(f"跳过重复告警: {dedup_key}")
                    continue

                rule_names = ", ".join(r["name"] for r in triggered)
                _, sell_price, stop_loss = suggest_prices(stock_data, atr)

                if risk:
                    msg = (
                        f"🚨 **风控预警** {code} {stock_data['name']}\n"
                        f"**触发规则**: {rule_names}\n"
                        f"**当前价**: {stock_data['close']:.2f} | **成本**: {position['cost']:.2f}\n"
                        f"**止损价**: {stop_loss:.2f} | **ATR**: {atr:.2f}\n"
                        f"**风险提示**: 请立即评估是否需要止损\n"
                    )
                    sell_messages.append(msg)
                    pending_alerts.append({
                        "dedup_key": dedup_key, "code": code, "date": today_str,
                        "rule_ids": rule_ids, "rule_names": rule_names,
                        "trigger_type": "risk", "sell_score": round(sell_sc, 2),
                        "buy_score": 0, "price": stock_data["close"],
                        "cost": position["cost"], "message": msg,
                        "created_at": datetime.now(),
                    })
                elif sell_sc > 0:
                    pnl_pct = round((stock_data["close"] - position["cost"]) / position["cost"] * 100, 2) if position["cost"] > 0 else 0
                    msg = (
                        f"📉 **卖出信号** {code} {stock_data['name']}\n"
                        f"**触发规则**: {rule_names}\n"
                        f"**卖出评分**: {sell_sc:.2f}\n"
                        f"**当前价**: {stock_data['close']:.2f} | **成本**: {position['cost']:.2f} | **盈亏**: {pnl_pct:+.2f}%\n"
                        f"**建议卖出价**: {sell_price:.2f} | **ATR**: {atr:.2f}\n"
                    )
                    sell_messages.append(msg)
                    pending_alerts.append({
                        "dedup_key": dedup_key, "code": code, "date": today_str,
                        "rule_ids": rule_ids, "rule_names": rule_names,
                        "trigger_type": "sell", "sell_score": round(sell_sc, 2),
                        "buy_score": 0, "price": stock_data["close"],
                        "cost": position["cost"], "message": msg,
                        "created_at": datetime.now(),
                    })

            else:
                # 非持仓股票：只执行买入规则 → 评分函数排序
                position = {"has_pos": False, "cost": 0, "buy_date": None}
                ctx = engine.build_context(stock_data, position)
                risk, sell_sc, buy_sc, triggered = engine.run(ctx)

                if buy_sc <= 0 or not triggered:
                    continue

                # 统一评分 (spec REQ-003)
                s = oversold_bounce_score(
                    close=stock_data.get("close", 0),
                    ma5=stock_data.get("ma5", 0),
                    ma10=stock_data.get("ma10", 0),
                    ma20=stock_data.get("ma20", 0),
                    ma60=stock_data.get("ma60", 0),
                    volume=stock_data.get("volume", 0),
                    ma5_vol=stock_data.get("ma5_vol", 0),
                    high20=stock_data.get("high", 0),
                    amplitude=stock_data.get("amplitude", 0),
                    is_st=bool(stock_data.get("name", "").startswith(("ST", "*ST"))),
                )
                # 评分 <= 0 (剔除/0分) 不进入候选 (spec REQ-003 AC)
                if s <= 0:
                    continue

                rule_ids = sorted(r["rule_id"] for r in triggered)
                dedup_key = f"{code}|{today_str}|{rule_ids}"

                if db.alert_log.find_one({"dedup_key": dedup_key}):
                    continue

                rule_names = ", ".join(r["name"] for r in triggered)
                buy_price, sell_price, stop_loss = suggest_prices(stock_data, atr)
                detail = score_detail(
                    close=stock_data.get("close", 0),
                    ma5=stock_data.get("ma5", 0),
                    ma10=stock_data.get("ma10", 0),
                    ma20=stock_data.get("ma20", 0),
                    ma60=stock_data.get("ma60", 0),
                    volume=stock_data.get("volume", 0),
                    ma5_vol=stock_data.get("ma5_vol", 0),
                    high20=stock_data.get("high", 0),
                    amplitude=stock_data.get("amplitude", 0),
                    is_st=bool(stock_data.get("name", "").startswith(("ST", "*ST"))),
                )

                buy_candidates.append({
                    "code": code,
                    "name": stock_data["name"],
                    "buy_score": buy_sc,
                    "unified_score": s,
                    "score_detail": detail,
                    "price": stock_data["close"],
                    "atr": atr,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "stop_loss": stop_loss,
                    "rule_names": rule_names,
                    "rule_ids": rule_ids,
                    "dedup_key": dedup_key,
                    "triggered": triggered,
                })
        except Exception as e:
            failed_count += 1
            logging.warning(f"[RULE_ENGINE] 跳过 {code}（{name_map.get(code, '')}）处理异常: {e}")
            # spec REQ-003 exception table: 失败股票 >= 10% 终止本轮推荐
            if total > 0 and failed_count / total >= FAILURE_ABORT_RATIO:
                logging.error(
                    f"[RULE_ENGINE] 失败比例 {failed_count}/{total} >= {FAILURE_ABORT_RATIO:.0%}，终止本轮推荐"
                )
                return

    # 7. 买入信号按统一评分排序 (spec REQ-003: 按 oversold_bounce_score 降序)
    best = None
    if buy_candidates:
        buy_candidates.sort(key=lambda x: -x["unified_score"])
        best = buy_candidates[0] if buy_candidates else None
        logging.info(f"候选买入信号 {len(buy_candidates)} 只，最高分: "
                     f"{best['code']} {best['name']} score={best['unified_score']:.2f}")

    if best:
        detail = best["score_detail"]
        msg = (
            f"📈 **买入信号** {best['code']} {best['name']}\n"
            f"**统一评分**: {best['unified_score']:.0f}分"
            f"（BIAS5={detail['bias5']} 趋势={detail['trend']} "
            f"板块={detail['sector']} 情绪={detail['sentiment']}）\n"
            f"**触发规则**: {best['rule_names']}\n"
            f"**当前价**: {best['price']:.2f}\n"
            f"**建议买入价**: {best['buy_price']:.2f}（当前价 - ATR）\n"
            f"**目标卖出价**: {best['sell_price']:.2f}（当前价 + ATR）\n"
            f"**止损价**: {best['stop_loss']:.2f}（当前价 - 2倍ATR）\n"
        )

        sell_messages.append(msg)
        pending_alerts.append({
            "dedup_key": best["dedup_key"], "code": best["code"],
            "date": today_str, "rule_ids": best["rule_ids"],
            "rule_names": best["rule_names"], "trigger_type": "buy",
            "sell_score": 0, "buy_score": round(best["unified_score"], 2),
            "score_detail": best["score_detail"],
            "price": best["price"], "cost": 0, "message": msg,
            "created_at": datetime.now(),
        })

    # 8. 推送钉钉，成功后才写告警日志
    if pending_alerts:
        title = f"交易规则触发 ({len(pending_alerts)} 条)"
        content = "\n---\n".join(sell_messages)
        if send_dingtalk_message(title, content):
            for doc in pending_alerts:
                db.alert_log.insert_one(doc)
            logging.info(f"推送成功，记录 {len(pending_alerts)} 条告警")
        else:
            logging.warning(f"推送失败，未记录 {len(pending_alerts)} 条告警，下次重试")
    else:
        logging.info("本轮未触发任何规则")


if __name__ == "__main__":
    Log("rule_engine", log_type=Log.TYPE_FILE, level=logging.INFO)
    pid_file = os.path.join(home(), 'apps', 'api', 'var', 'run', 'rule_engine.pid')
    single = ScriptSingle(pid_file)

    if single.is_running():
        logging.error('there is script lock {}'.format(pid_file))
        sys.exit(0)
    run_rules_for_holdings()
