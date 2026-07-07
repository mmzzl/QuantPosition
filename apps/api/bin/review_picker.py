import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import date
from typing import List, Dict, Any, Optional
from database import get_db
from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from services.review_service import ReviewService


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
        if pure.startswith(("300", "688")):
            continue
        if "ST" in name or "\u9000" in name:
            continue
        stocks.append({"code": pure, "name": name})
    logging.info(f"Loaded {len(stocks)} valid stocks (excl 300/688/ST/indexes)")
    return stocks


def calc_score(r: Dict[str, Any]) -> float:
    if r["conclusion"] == "\u8df3\u8fc7":
        return -1

    score = 50.0

    pos = {"\u4f4e\u4f4d": 25, "\u4e2d\u6bb5": 15, "\u9ad8\u4f4d": -30}
    score += pos.get(r["position"], 0)

    vwap = {"\u5f3a\u52bf": 25, "\u632f\u8361": 5, "\u5f31\u52bf": -20}
    score += vwap.get(r["vwap_status"], 0)

    vol = {"\u6d17\u76d8": 20, "\u632f\u8361": 5, "\u8bd5\u76d8": 5, "\u51fa\u8d27": -25}
    score += vol.get(r["volume_signal"], 0)

    good_patterns = {"\u5c3e\u76d8\u62a2\u7b79\u578b", "\u5355\u8fb9\u632f\u8361\u4e0a\u884c", "U\u578b\u6d17\u76d8\u5206\u65f6"}
    bad_patterns = {"M\u5934\u5206\u65f6", "\u9ad8\u5f00\u4f4e\u8d70\u9634\u8dcc\u578b", "\u65e9\u76d8\u8109\u51b2\u5168\u5929\u56de\u843d"}
    if r["pattern"] in good_patterns:
        score += 20
    elif r["pattern"] in bad_patterns:
        score -= 20
    elif r["pattern"] == "\u632f\u8361\u5e73\u8861\u5f62\u6001":
        score += 5

    tail = {"\u62a2\u7b79": 10, "\u65e0\u91cf\u6a2a\u76d8": 0, "\u653e\u91cf\u8df3\u6c34": -15}
    score += tail.get(r["tail_signal"], 0)

    if r["conclusion"] == "\u6301\u6709":
        score += 10
    elif r["conclusion"] == "\u5356\u51fa":
        score -= 25

    return max(0, min(100, score))


def build_message(results: List[Dict]) -> str:
    scored = []
    for r in results:
        s = calc_score(r)
        if s >= 0:
            scored.append((s, r))
    if not scored:
        return "\u660e\u65e5\u5173\u6ce8", "\u4eca\u65e5\u65e0\u660e\u663e\u4e70\u5165\u4fe1\u53f7\u7684\u80a1\u7968"
    scored.sort(key=lambda x: x[0], reverse=True)
    top_s, top_r = scored[0]

    lines = [
        "\u2501" * 20,
        f"\U0001f50d **{top_r['code']} {top_r['name']}**",
        f"\U0001f4c8 \u4e70\u5165\u8bc4\u5206\uff1a**{top_s:.0f}/100**",
        f"\U0001f4cc \u65e5\u7ebf\u5b9a\u4f4d\uff1a{top_r['position']}",
        f"\U0001f4ca \u5747\u4ef7\u5206\u6790\uff1a{top_r['vwap_status']}",
        f"\U0001f4cb \u91cf\u80fd\u5206\u6790\uff1a{top_r['volume_signal']}",
        f"\U0001f50e \u5206\u65f6\u5f62\u6001\uff1a{top_r['pattern']}",
        f"\U0001f319 \u5c3e\u76d8\u4fe1\u53f7\uff1a{top_r['tail_signal']}",
        f"\u23f0 \u7b56\u7565\uff1a{top_r['strategy']}",
        "---",
        f"\u5171\u8bc4\u5206 {len(scored)} \u53ea\u80a1\u7968\uff0c\u5f53\u524d\u7b2c\u4e00",
    ]
    title = f"\u660e\u65e5\u5173\u6ce8 ({top_r['code']})"
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

    scored = [(calc_score(r), r) for r in results if calc_score(r) >= 0]
    scored.sort(key=lambda x: x[0], reverse=True)
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
