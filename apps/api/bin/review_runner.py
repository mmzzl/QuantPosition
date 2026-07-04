# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
from datetime import datetime, date
from database import get_db
from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from services.review_service import ReviewService


def get_target_stocks(db):
    today_start = datetime.now().strftime("%Y-%m-%d 00:00")
    today_end = datetime.now().strftime("%Y-%m-%d 23:59")

    holdings = list(db.holdings.find({}, {"code": 1, "name": 1, "_id": 0}))
    logging.info(f"持仓数量: {len(holdings)}")

    buy_alerts = list(db.alert_log.find({
        "trigger_type": "buy",
        "created_at": {"$gte": today_start, "$lte": today_end}
    }, {"code": 1, "_id": 0}))
    logging.info(f"今日推荐买入: {len(buy_alerts)}")

    seen = set()
    result = []
    for h in holdings:
        code = h.get("code", "")
        if code and code not in seen:
            seen.add(code)
            result.append({"code": code, "name": h.get("name", "")})
    for a in buy_alerts:
        code = a.get("code", "")
        if code and code not in seen:
            seen.add(code)
            result.append({"code": code, "name": ""})
    return result


def build_dingtalk_message(results):
    if not results:
        return "收盘分时复盘", "今日无持仓和推荐股票需要分析"

    lines = []
    for r in results:
        if r["conclusion"] == "跳过":
            continue

        emoji_map = {"卖出": "\U0001f534", "持有": "\U0001f7e2", "观望": "\U0001f7e1"}
        icon = emoji_map.get(r["conclusion"], "\u26aa")
        vwap_icon = "\u2705" if r["vwap_status"] == "强势" else ("\u274c" if r["vwap_status"] == "弱势" else "\u2795")
        tail_icon = "\u2705" if r["tail_signal"] == "抢筹" else ("\u274c" if r["tail_signal"] == "放量跳水" else "\u2795")

        lines.append("\u2501" * 25)
        lines.append(f"{icon} **{r['code']} {r['name']}**")
        lines.append(f"\U0001f4cc 日线定位：{r['position']}")
        lines.append(f"\U0001f4c8 均价分析：{r['vwap_status']} {vwap_icon}")
        lines.append(f"\U0001f4ca 量能分析：{r['volume_signal']}")
        lines.append(f"\U0001f50d 分时形态：{r['pattern']}")
        lines.append(f"\U0001f319 尾盘信号：{r['tail_signal']} {tail_icon}")
        lines.append(f"\U0001f3af **结论：{r['conclusion']}**")
        lines.append(f"\U0001f4a1 {r['strategy']}")

    if not lines:
        return "收盘分时复盘", "今日无持仓和推荐股票需要分析"

    title = f"收盘分时复盘 ({len(results)} 只)"
    content = "\n".join(lines)
    return title, content


def main():
    Log("review_runner", log_type=Log.TYPE_FILE, level=logging.INFO)
    logging.info("开始收盘分时复盘...")

    db = get_db()
    targets = get_target_stocks(db)
    if not targets:
        logging.info("无目标股票，跳过分析")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    results = []
    for t in targets:
        try:
            result = ReviewService.analyze(t["code"], t["name"], today_str)
            results.append(result)
            logging.info(f"分析完成: {t['code']} {t['name']} \u2192 {result['conclusion']}")
        except Exception as e:
            logging.error(f"分析失败: {t['code']} {t['name']}: {e}")

    from bin.rule_engine import send_dingtalk_message
    title, content = build_dingtalk_message(results)
    send_dingtalk_message(title, content)
    logging.info(f"钉钉推送完成: {title}")


if __name__ == "__main__":
    pid_file = os.path.join(home(), "apps", "api", "var", "run", "review_runner.pid")
    single = ScriptSingle(pid_file)
    if single.is_running():
        logging.error("script lock {}".format(pid_file))
        sys.exit(0)
    main()
