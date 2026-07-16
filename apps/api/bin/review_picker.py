import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import date
from typing import List, Dict, Any
from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from services.review_service import ReviewService
from services.stock_scorer import StockScorer


def load_stocks(path: str) -> List[Dict[str, str]]:
    import pandas as pd
    df = pd.read_csv(path)
    stocks = []
    for _, row in df.iterrows():
        code = str(row.get("code", "")).strip()
        name = str(row.get("code_name", "")).strip()
        pure = code.split(".")[-1]
        if not (pure.isdigit() and len(pure) == 6):
            continue
        if not (code.startswith("sh.6") or code.startswith("sz.0") or code.startswith("bj.8")):
            continue
        if pure.startswith(("300", "688")):
            continue
        if "ST" in name or "\u9000" in name:
            continue
        stocks.append({"code": pure, "name": name})
    logging.info(f"Loaded {len(stocks)} valid stocks (excl 300/688/ST/indexes)")
    return stocks


INTENTION_BONUS = {
    "吸筹": 15,
    "洗盘": 10,
    "假出货诱空": 10,
    "高位震荡": 0,
    "出货风险": -999,
    "真出货": -999,
    "震荡": 0,
}

INTENTION_ICON = {
    "吸筹": "\U0001f4b0",
    "洗盘": "\U0001f300",
    "假出货诱空": "\U0001f92b",
    "真出货": "\u26a0\ufe0f",
    "出货风险": "\u26a0\ufe0f",
}


def calc_score(r: Dict[str, Any]) -> float:
    if "scorer_total" in r:
        return r["scorer_total"]
    intention = r.get("main_force_intention", "")
    bonus = INTENTION_BONUS.get(intention, 0)
    if bonus < 0:
        r["scorer_total"] = -1
        return -1
    scorer = StockScorer()
    result = scorer.score(r["code"], r["name"], r.get("date", date.today().strftime("%Y-%m-%d")))
    r["scorer_total"] = result["total"] + bonus
    r["intention_bonus"] = bonus
    return r["scorer_total"]


def build_message(results: List[Dict]) -> str:
    scored = []
    for r in results:
        s = calc_score(r)
        if s >= 0:
            scored.append((s, r))
    if not scored:
        return "明日关注", "今日无明显买入信号的股票"
    scored.sort(key=lambda x: x[0], reverse=True)
    top_s, top_r = scored[0]

    intention = top_r.get("main_force_intention", "")
    icon = INTENTION_ICON.get(intention, "\U0001f9d0")
    confidence = top_r.get("intention_confidence", "")
    conf_icon = {"高": "\U0001f7e2", "中": "\U0001f7e1", "低": "\U0001f534"}.get(confidence, "")

    lines = [
        "\u2501" * 20,
        f"{icon} **{top_r['code']} {top_r['name']}**",
        f"\U0001f3af 主力意图：**{intention}** {conf_icon}",
        f"\U0001f4c8 综合评分：**{top_s:.0f}分**",
        top_r.get("intention_detail", ""),
        f"\U0001f4cc 日线定位：{top_r['position']}  |  日线量能：{top_r.get('daily_vol_pattern', '')}",
        f"\U0001f4ca 均价分析：{top_r['vwap_status']}  |  量能信号：{top_r['volume_signal']}",
        f"\U0001f50e 分时形态：{top_r['pattern']}  |  尾盘：{top_r['tail_signal']}",
        "",
        f"\u23f0 {top_r['strategy']}",
        "---",
        f"\U0001f50d 共评分 {len(scored)} 只，当前第1 | 意图置信度：{confidence}",
    ]
    title = f"明日关注 ({top_r['code']} {intention})"
    return title, "\n".join(lines)


def main():
    Log("review_picker", log_type=Log.TYPE_FILE, level=logging.INFO)
    logging.info("\u5f00\u59cb\u6536\u76d8\u9009\u80a1...")

    path = os.path.join(home(), "apps", "api", "data", "all_stock.csv")
    stocks = load_stocks(path)
    if not stocks:
        logging.info("\u65e0\u6709\u6548\u80a1\u7968\uff0c\u8df3\u8fc7\u5206\u6790")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    results = []
    results_lock = Lock()
    total = len(stocks)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {}
        for stk in stocks:
            futures[executor.submit(ReviewService.analyze, stk["code"], stk["name"], today_str)] = stk

        for i, future in enumerate(as_completed(futures)):
            stk = futures[future]
            try:
                r = future.result()
                with results_lock:
                    results.append(r)
                if r["conclusion"] != "\u8df3\u8fc7":
                    logging.debug(f"Scored {stk['code']} {stk['name']}: {calc_score(r):.0f}")
            except Exception as e:
                logging.error(f"Error analyzing {stk['code']} {stk['name']}: {e}")

            if (i + 1) % 500 == 0:
                logging.info(f"Progress: {i+1}/{total}")

    scored = sorted(
        [(calc_score(r), r) for r in results],
        key=lambda x: x[0], reverse=True
    )
    scored = [(s, r) for s, r in scored if s >= 0]
    logging.info(f"Scored {len(scored)} stocks, top 5: {[(r['code'], int(s)) for s, r in scored[:5]]}")

    title, content = build_message(results)
    from bin.rule_engine import send_dingtalk_message
    send_dingtalk_message(title, content)
    logging.info(f"DingTalk pushed: {title}")


if __name__ == "__main__":
    pid_file = os.path.join(home(), "apps", "api", "var", "run", "review_picker.pid")
    single = ScriptSingle(pid_file)
    if single.is_running():
        logging.error("script lock {}".format(pid_file))
        sys.exit(0)
    main()
