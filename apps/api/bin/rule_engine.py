# -*- coding: utf-8 -*-
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import socket
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from systems.logs import Log

logger = logging.getLogger(__name__)
from systems.single import ScriptSingle
from systems.sys import home
from services.stock_scorer import StockScorer




from services.notification_service import send_dingtalk_message


class StockRuleEngine:
    def __init__(self, rules: List[Dict]):
        self.rules = sorted(rules, key=lambda r: r.get("priority", 99))

    def run(self, ctx: dict) -> tuple:
        risk_triggered = False
        sell_score = 0.0
        buy_score = 0.0
        triggered_rules = []

        for rule in self.rules:
            if not rule.get("enabled", True):
                continue
            try:
                ok = bool(eval(rule["condition"], {"__builtins__": {}}, ctx))
            except Exception as e:
                logging.error(f"规则执行错误: {e}, 规则: {rule['name']}")
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

    # Wilder's smooth TR, +DM, -DM
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

    # Wilder's smooth ADX
    adx = sum(dxs[:period]) / period
    for i in range(period, len(dxs)):
        adx = (adx * (period - 1) + dxs[i]) / period
    return round(adx, 1)


def load_stock_klines(db, codes, days=60):
    """批量加载K线数据"""
    now = datetime.now()
    start_str = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d") + " 23:59"
    klines_raw = list(db.stock_kline.find({
        "code": {"$in": codes},
        "frequency": 9,
        "date": {"$gte": start_str, "$lte": end_str}
    }).sort("date", 1))
    stock_klines = {}
    for k in klines_raw:
        stock_klines.setdefault(k["code"], []).append(k)
    return stock_klines


def build_stock_indicators(klines):
    """从K线数据计算技术指标，返回 stock_data 字典"""
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


def filter_trend_up(db, exclude_codes=None):
    """全市场扫描，排除ST，双均线过滤趋势向上（MA5 > MA10 且 MA5 上升）"""
    exclude_codes = exclude_codes or set()

    # 获取所有非ST股票代码
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
              and not c.startswith(("300", "301", "688"))]  # 排除创业板和科创板

    logging.info(f"[RULE_ENGINE] 全市场非ST股票: {len(non_st)} 只")

    # 批量加载K线
    stock_klines = load_stock_klines(db, non_st)

    # 双均线过滤：MA5 > MA10 且 MA5 连续3天上升
    trend_up = []
    for code, klines in stock_klines.items():
        if len(klines) < 20:
            continue
        closes = [k["close"] for k in klines]
        ma5_now = calc_sma(closes, 5)
        ma10_now = calc_sma(closes, 10)
        # MA5 > MA10 表示短期趋势向上
        if ma5_now <= ma10_now:
            continue
        # 检查 MA5 是否在上升（最近3天）
        if len(closes) >= 8:
            ma5_3d_ago = sum(closes[-8:-3]) / 5
            if ma5_now <= ma5_3d_ago:
                continue
        trend_up.append(code)

    logging.info(f"[RULE_ENGINE] 趋势向上（MA5>MA10且上升）: {len(trend_up)} 只")
    return trend_up, stock_klines, name_map


def suggest_prices(stock_data, atr):
    """基于 ATR 动态计算建议买入/卖出价格
    按 ATR% 自动调整倍数：波动率低时多倍ATR，波动率高时少倍ATR
    目标：买卖价差稳定在 ~3%，止损失在 ~6%
    """
    close = stock_data["close"]
    atr_pct = atr / close if close > 0 else 0.03
    mult = max(0.3, min(3.0, 0.03 / atr_pct)) if atr_pct > 0 else 1.0
    buy_price = round(close - atr * mult, 2)
    sell_price = round(close + atr * mult, 2)
    stop_loss = round(close - 2 * atr * mult, 2)
    return buy_price, sell_price, stop_loss


def run_rules_for_holdings():
    """从 MongoDB 获取持仓和 K 线数据，执行所有启用规则

    持仓 → has_pos=True（评估卖出/风控）
    全市场 → 排除ST → 双均线过滤 → has_pos=False（评估买入）

    买入信号按评分排序，只推送最高分的那只
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

    # 3. 买入候选池：全市场扫描 + 双均线过滤
    stock_klines_all = {}
    name_map = {}
    if has_buy_rule:
        trend_up_codes, stock_klines_all, name_map = filter_trend_up(db, exclude_codes=holding_codes)
        logging.info(f"买入候选池: {len(trend_up_codes)} 只（趋势向上，排除持仓）")
    else:
        # 没有买入规则时，只需加载持仓股票的K线
        if holdings:
            stock_klines_all = load_stock_klines(db, list(holding_codes))
            for s in db.sector_stocks.find({}, {"stock_code": 1, "stock_name": 1}):
                code = s.get("stock_code", "").split(".")[-1]
                if code:
                    name_map[code] = s.get("stock_name", "")

    # 4. 合并所有需要扫描的股票代码
    all_codes = list(holding_codes)
    if has_buy_rule:
        all_codes = list(set(all_codes) | set(trend_up_codes))
    if not all_codes:
        logging.info("没有股票需要扫描")
        return

    # 5. 补充持仓股票的K线数据（如果没有加载过）
    missing_codes = [c for c in holding_codes if c not in stock_klines_all]
    if missing_codes:
        extra_klines = load_stock_klines(db, missing_codes)
        stock_klines_all.update(extra_klines)

    engine = StockRuleEngine(rules)
    buy_candidates = []   # 存放所有买入信号，用于排序
    sell_messages = []    # 存放卖出/风控信号
    pending_alerts = []

    # 6. 执行规则扫描
    total = len(all_codes)
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

                today_str = datetime.now().strftime("%Y-%m-%d")
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
                # 非持仓股票：只执行买入规则
                position = {"has_pos": False, "cost": 0, "buy_date": None}
                ctx = engine.build_context(stock_data, position)
                risk, sell_sc, buy_sc, triggered = engine.run(ctx)

                if buy_sc <= 0 or not triggered:
                    continue

                today_str = datetime.now().strftime("%Y-%m-%d")
                rule_ids = sorted(r["rule_id"] for r in triggered)
                dedup_key = f"{code}|{today_str}|{rule_ids}"

                if db.alert_log.find_one({"dedup_key": dedup_key}):
                    continue

                rule_names = ", ".join(r["name"] for r in triggered)
                buy_price, sell_price, stop_loss = suggest_prices(stock_data, atr)

                buy_candidates.append({
                    "code": code,
                    "name": stock_data["name"],
                    "buy_score": buy_sc,
                    "price": stock_data["close"],
                    "atr": atr,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "stop_loss": stop_loss,
                    "rule_names": rule_names,
                    "rule_ids": rule_ids,
                    "dedup_key": dedup_key,
                    "stock_data": stock_data,
                    "triggered": triggered,
                })
        except Exception as e:
            logging.warning(f"[RULE_ENGINE] 跳过 {code}（{name_map.get(code, '')}）处理异常: {e}")

    # 7. 买入信号评分 + 排序，只保留最高分
    best = None
    if buy_candidates:
        socket.setdefaulttimeout(30)
        scorer = StockScorer()
        total_candidates = len(buy_candidates)
        for i, c in enumerate(buy_candidates, 1):
            logging.info(f"[RULE_ENGINE] 评分进度: {i}/{total_candidates} {c['code']} {c.get('name', '')}")
            try:
                result = scorer.score(c["code"], c.get("name", ""))
                c["scorer_score"] = result["total"]
                c["scorer_level"] = result["level"]
            except Exception as e:
                logging.warning(f"[RULE_ENGINE] {c['code']} 评分异常: {e}")
                c["scorer_score"] = -1
                c["scorer_level"] = "C"

        buy_candidates = [c for c in buy_candidates if c["scorer_score"] >= 0]
        buy_candidates.sort(key=lambda x: x["scorer_score"], reverse=True)
        best = buy_candidates[0] if buy_candidates else None

        if best["scorer_score"] < 60:
            logging.info(f"Best candidate {best['code']} {best['name']} score={best['scorer_score']} < 60,skipping")
            buy_candidates = []
            best = None

    if best:
        msg = (
            f"📈 **买入信号** {best['code']} {best['name']}\n"
            f"**短线评分**: {best['scorer_score']:.0f}分（等级{best['scorer_level']}）\n"
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
            "sell_score": 0, "buy_score": round(best["scorer_score"], 2),
            "price": best["price"], "cost": 0, "message": msg,
            "created_at": datetime.now(),
        })
        logging.info(f"最高分买入信号: {best['code']} {best['name']} score={best['scorer_score']:.2f}（共 {len(buy_candidates)} 只候选）")

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
