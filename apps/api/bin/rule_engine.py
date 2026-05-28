# -*- coding: utf-8 -*-
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import hmac
import base64
import time
import logging
import requests
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, quote
from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home




def send_dingtalk_message(title: str, content: str):
    """发送钉钉消息"""
    try:
        import sys
        sys.path.insert(0, __file__)
        from database import get_db
        db = get_db()
        settings = db.system_settings.find_one({"_id": "global"})
        webhook = (settings or {}).get("dingtalk_webhook", "")
        secret = (settings or {}).get("dingtalk_secret", "")

        if not webhook:
            logging.warning("钉钉 webhook 未配置")
            return False

        timestamp = str(round(time.time() * 1000))
        if secret:
            sign_str = f"{timestamp}\n{secret}"
            sign = base64.b64encode(
                hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).digest()
            ).decode("utf-8")
            webhook += f"&timestamp={timestamp}&sign={quote(sign)}"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}"
            }
        }
        resp = requests.post(webhook, json=payload, timeout=5)
        result = resp.json()
        logging.info(f"钉钉推送结果: {result}")
        return result.get("errcode") == 0
    except Exception as e:
        logging.error(f"钉钉推送失败: {e}")
        return False


class StockRuleEngine:
    def __init__(self, rules: List[Dict]):
        self.rules = sorted(rules, key=lambda r: r["priority"])

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
                    logging.info(f"风控触发: {rule['name']}")
                elif rule["type"] == "sell":
                    sell_score += rule.get("weight", 0)
                    logging.info(f"卖出触发: {rule['name']}, weight={rule['weight']}")
                elif rule["type"] == "buy":
                    buy_score += rule.get("weight", 0)
                    logging.info(f"买入触发: {rule['name']}, weight={rule['weight']}")

        return risk_triggered, sell_score, buy_score, triggered_rules

    @staticmethod
    def build_context(stock_data: dict, position: Optional[dict]) -> dict:
        if position is None:
            position = {}

        today = datetime.now().date()
        today_num = today.toordinal()

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
            "rsi": stock_data.get("rsi", 50),
            "atr": stock_data.get("atr", 0),
            "adx": stock_data.get("adx", 0),
            "amplitude": stock_data.get("amplitude", 0),
            "has_pos": position.get("has_pos", False),
            "cost": position.get("cost", 0),
            "buy_date": buy_date_num,
            "today": today_num,
        }
        return ctx


def run_rules_for_holdings():
    """从 MongoDB 获取持仓和 K 线数据，执行所有启用规则

    持仓 → has_pos=True（评估卖出/风控）
    选股候选池 → has_pos=False（评估买入）
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
    logging.info(f"持仓数量: {len(holding_codes)}")

    # 3. 构建买入候选池（用于评估 buy 规则）
    buy_candidates = {}  # code -> {name, user_id}
    if has_buy_rule:
        # 从最新的新闻选股缓存拿候选股票
        cache = list(db.news_selection_cache.find({}).sort("expected_return", -1).limit(100))
        for c in cache:
            if c["code"] not in holding_codes:
                buy_candidates[c["code"]] = {
                    "name": c.get("name", ""),
                    "user_id": "system",
                }
        # 再从双均线选股结果补充
        selections = list(db.stock_selections.find(
            {"strategy": "dual_moving_average"}
        ).sort("selection_date", -1).limit(100))
        for s in selections:
            code = s.get("code", "")
            if code and code not in holding_codes and code not in buy_candidates:
                buy_candidates[code] = {
                    "name": s.get("name", ""),
                    "user_id": "system",
                }
        logging.info(f"买入候选池: {len(buy_candidates)} 只")

    # 4. 合并所有需要扫描的股票代码
    all_codes = list(holding_codes | set(buy_candidates.keys()))
    if not all_codes:
        logging.info("没有股票需要扫描")
        return

    # 5. 获取 K 线数据（最近 60 天）
    now = datetime.now()
    start_str = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d") + " 23:59"

    klines_raw = list(db.stock_kline.find({
        "code": {"$in": all_codes},
        "frequency": 9,
        "date": {"$gte": start_str, "$lte": end_str}
    }).sort("date", 1))

    stock_klines = {}
    for k in klines_raw:
        stock_klines.setdefault(k["code"], []).append(k)

    engine = StockRuleEngine(rules)
    triggered_messages = []
    pending_alerts = []

    # 6. 构建持仓代码→持仓信息映射
    holding_map = {h["code"]: h for h in holdings}

    # 7. 执行规则扫描
    for code in all_codes:
        klines = stock_klines.get(code, [])
        if not klines:
            continue

        closes = [k["close"] for k in klines]
        volumes = [k["volume"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]

        # 计算指标
        def sma(data, n):
            return sum(data[-n:]) / n if len(data) >= n else data[-1]

        def calc_rsi(prices, period=14):
            if len(prices) < period + 1:
                return 50
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            gains = [d if d > 0 else 0 for d in deltas[-period:]]
            losses = [-d if d < 0 else 0 for d in deltas[-period:]]
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            if avg_loss == 0:
                return 100
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))

        def calc_atr(highs, lows, closes, period=14):
            if len(closes) < period + 1:
                return (highs[-1] - lows[-1]) if (highs[-1] - lows[-1]) > 0 else 0
            trs = []
            for i in range(1, len(highs)):
                tr = max(highs[i] - lows[i],
                         abs(highs[i] - closes[i-1]),
                         abs(lows[i] - closes[i-1]))
                trs.append(tr)
            return sum(trs[-period:]) / period

        last_close = closes[-1]
        amplitude = (highs[-1] - lows[-1]) / last_close if last_close > 0 else 0

        stock_data = {
            "close": last_close,
            "volume": volumes[-1],
            "ma5": sma(closes, 5),
            "ma10": sma(closes, 10),
            "ma20": sma(closes, 20),
            "ma60": sma(closes, 60),
            "ma5_vol": sma(volumes, 5),
            "last_close": closes[-2] if len(closes) >= 2 else closes[-1],
            "high": max(highs[-20:]),
            "low": min(lows[-20:]),
            "open": klines[-1].get("open", 0),
            "rsi": calc_rsi(closes),
            "atr": calc_atr(highs, lows, closes),
            "adx": 25,  # ADX 计算复杂，默认 25（回测中用 backtrader 计算精确值）
            "amplitude": amplitude,
        }

        stock_data["name"] = (
            holding_map[code].get("name", "")
            if code in holding_map
            else buy_candidates.get(code, {}).get("name", "")
        )

        if code in holding_map:
            h = holding_map[code]
            position = {
                "has_pos": True,
                "cost": h.get("average_cost", 0),
                "buy_date": h["created_at"].date() if isinstance(h.get("created_at"), datetime) else None,
            }
            user_id = h.get("user_id", "?")
        else:
            position = {"has_pos": False, "cost": 0, "buy_date": None}
            user_id = buy_candidates.get(code, {}).get("user_id", "system")

        ctx = engine.build_context(stock_data, position)
        risk, sell_sc, buy_sc, triggered = engine.run(ctx)

        if triggered:
            today_str = datetime.now().strftime("%Y-%m-%d")
            rule_ids = sorted(r["rule_id"] for r in triggered)
            dedup_key = f"{code}|{today_str}|{rule_ids}"

            # 查重：同股票+同日+同规则不重复告警
            if db.alert_log.find_one({"dedup_key": dedup_key}):
                logging.info(f"跳过重复告警: {dedup_key}")
                continue

            rule_names = ", ".join(r["name"] for r in triggered)
            status = "🚨 风控" if risk else "📈 买入" if buy_sc > 0 else "📉 卖出"
            msg = (
                f"{status} **{code}** {stock_data.get('name', '')}\n"
                f"**触发规则**: {rule_names}\n"
                f"**卖出分**: {sell_sc:.2f} | **买入分**: {buy_sc:.2f}\n"
                f"**当前价**: {stock_data['close']:.2f} | **成本**: {position['cost']:.2f}\n"
                f"**均线**: MA5={stock_data['ma5']:.2f} MA10={stock_data['ma10']:.2f}\n"
            )
            if risk:
                msg = f"🚨 **风控触发**\n" + msg

            triggered_messages.append(msg)
            pending_alerts.append({
                "dedup_key": dedup_key,
                "code": code,
                "date": today_str,
                "rule_ids": rule_ids,
                "rule_names": rule_names,
                "trigger_type": "risk" if risk else ("buy" if buy_sc > 0 else "sell"),
                "sell_score": round(sell_sc, 2),
                "buy_score": round(buy_sc, 2),
                "price": stock_data["close"],
                "cost": position["cost"],
                "message": msg,
                "created_at": datetime.now(),
            })

    # 8. 推送钉钉，成功后才写告警日志
    if pending_alerts:
        title = f"交易规则触发通知 ({len(pending_alerts)} 条)"
        content = "\n---\n".join(triggered_messages)
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
