import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pymongo import UpdateOne

from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from database import get_db


TENCENT_MAX = 100


def _tencent_5m_kline(code: str, count: int = TENCENT_MAX) -> Optional[List[Dict]]:
    market = "bj" if code.startswith("8") else ("sh" if code.startswith(("6", "5")) else "sz")
    try:
        r = requests.get(
            "https://ifzq.gtimg.cn/appstock/app/kline/mkline",
            params={"param": f"{market}{code},m5,,{count}"},
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"tencent HTTP error for {code}: {e}")
        return None
    except ValueError as e:
        logging.error(f"tencent JSON decode error for {code}: {e}, body={r.text[:200]}")
        return None

    if not d.get("data"):
        return []

    data = list(d["data"].values())[0]
    bars = data.get("m5")
    if not bars or not isinstance(bars, list):
        return []

    today_str = date.today().strftime("%Y-%m-%d")
    records = []
    for bar in bars:
        if not isinstance(bar, (list, tuple)) or len(bar) < 6:
            continue
        raw_time = str(bar[0]).strip()
        if not raw_time:
            continue
        try:
            dt = datetime.strptime(raw_time, "%Y%m%d%H%M")
            date_fmt = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if date_fmt[:10] != today_str:
            continue
        try:
            o, c, h, l = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
            v = int(float(bar[5])) if bar[5] else 0
            amt = float(bar[6]) if len(bar) > 6 and bar[6] else 0.0
        except (ValueError, TypeError):
            continue
        records.append({
            "code": code,
            "date": date_fmt,
            "open": o,
            "close": c,
            "high": h,
            "low": l,
            "volume": v,
            "amount": amt,
            "crawl_time": datetime.now().isoformat(),
        })
    return records


class MinuteKlineScraper:
    def __init__(self):
        self.collection = get_db()["stock_kline_5m"]

    def _get_all_stock_codes(self) -> List[str]:
        codes = set()
        path = os.path.join(home(), "apps", "api", "data", "all_stock.csv")
        try:
            import pandas as pd
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                if code:
                    pure = code.split(".")[-1]
                    if pure.isdigit():
                        codes.add(pure)
            logging.info(f"Loaded {len(codes)} stock codes from all_stock.csv")
        except Exception as e:
            logging.error(f"Failed to load all_stock.csv: {e}")
            raise
        return sorted(list(codes))

    def _fetch_5m_kline(self, code: str) -> List[Dict[str, Any]]:
        records = _tencent_5m_kline(code)
        if records is None:
            return None
        logging.debug(f"tencent 5m {code}: {len(records)} bars")
        return records

    def save_klines(self, records: List[Dict[str, Any]]):
        if not records:
            return
        try:
            today_str = date.today().strftime("%Y-%m-%d")
            codes = set(r["code"] for r in records)
            for c in codes:
                self.collection.delete_many({"code": c, "date": {"$regex": f"^{today_str}"}})

            operations = [
                UpdateOne(
                    {"code": r["code"], "date": r["date"]},
                    {"$set": r},
                    upsert=True,
                )
                for r in records
            ]
            if operations:
                result = self.collection.bulk_write(operations, ordered=False)
                logging.info(f"Saved {result.upserted_count + result.modified_count}/{len(records)} bars")
        except Exception as e:
            logging.error(f"Failed to save {len(records)} bars: {e}")

    def fetch_all(self):
        codes = self._get_all_stock_codes()
        total = len(codes)
        workers = 10
        results = {"success": 0, "skipped": 0, "failed": 0}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._fetch_5m_kline, code): code for code in codes}
            pending = []
            pending_lock = Lock()

            for i, future in enumerate(as_completed(futures)):
                code = futures[future]
                try:
                    records = future.result()
                    if records is None:
                        results["failed"] += 1
                    elif not records:
                        results["skipped"] += 1
                    else:
                        with pending_lock:
                            pending.extend(records)
                        results["success"] += 1
                except Exception as e:
                    logging.error(f"Error processing {code}: {e}")
                    results["failed"] += 1

                if len(pending) >= 2000:
                    with pending_lock:
                        self.save_klines(pending)
                        pending = []

                if (i + 1) % 500 == 0:
                    logging.info(f"Progress: {i+1}/{total}, success={results['success']}, skipped={results['skipped']}, failed={results['failed']}")

            with pending_lock:
                if pending:
                    self.save_klines(pending)

        logging.info(f"5m kline fetch completed: total={total}, success={results['success']}, skipped={results['skipped']}, failed={results['failed']}")


if __name__ == "__main__":
    Log("review_spider", log_type=Log.TYPE_FILE, level=logging.INFO)
    pid_file = os.path.join(home(), "apps", "api", "var", "run", "review_spider.pid")
    single = ScriptSingle(pid_file)
    if single.is_running():
        logging.error("script lock {}".format(pid_file))
        sys.exit(0)
    scraper = MinuteKlineScraper()
    scraper.fetch_all()
