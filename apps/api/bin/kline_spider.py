import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import traceback
import requests
import pandas as pd
import logging

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pymongo import UpdateOne

from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from database import get_db


TENCENT_MAX = 320


TODAY_FLAG = " 15:00"


def _tencent_kline(code: str, count: int = TENCENT_MAX) -> Optional[List[Dict]]:
    market = "sh" if code.startswith(("6", "5")) else "sz"
    try:
        r = requests.get(
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            params={"param": f"{market}{code},day,,,{count},qfq"},
            timeout=10,
        )
        d = r.json()
    except Exception as e:
        logging.error(f"tencent HTTP error for {code}: {e}")
        return None

    if not (d.get("data")):
        return []

    data = list(d["data"].values())[0]
    bars = data.get("qfqday") or data.get("day")
    if not bars or not isinstance(bars, list):
        return []

    records = []
    for bar in bars:
        if not isinstance(bar, (list, tuple)) or len(bar) < 6:
            continue
        date_str = str(bar[0]).strip()
        if not date_str:
            continue
        try:
            o, c, h, l = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
            v = int(float(bar[5])) if bar[5] else 0
        except (ValueError, TypeError):
            continue
        records.append({
            "code": code,
            "date": f"{date_str}{TODAY_FLAG}",
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "amount": 0.0,
            "frequency": 9,
            "adjust": "qfq",
            "crawl_time": datetime.now().isoformat(),
        })
    return records


class StockKlineScraper:
    def __init__(self):
        self.storage = get_db()["stock_kline"]

    @staticmethod
    def _cutoff_date() -> str:
        now = datetime.now()
        if now.hour < 15 or (now.hour == 15 and now.minute == 0):
            cutoff = now - timedelta(days=1)
        else:
            cutoff = now
        return cutoff.strftime("%Y-%m-%d")

    def _get_latest_bar_time(self, code: str, frequency: int) -> Optional[str]:
        try:
            doc = self.storage.find_one(
                {"code": code, "frequency": frequency},
                sort=[("date", -1)],
            )
            return doc.get("date") if doc else None
        except Exception as e:
            logging.warning(f"Failed to get latest bar time for {code}: {e}")
            return None

    def _get_all_stock_codes(self) -> List[str]:
        codes = set()
        path = os.path.join(home(), "apps", "api", "data", "all_stock.csv")
        try:
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

    def _fetch_kline(self, code: str) -> List[Dict[str, Any]]:
        records = _tencent_kline(code)
        if records is None:
            return None

        cutoff = self._cutoff_date()
        records = [r for r in records if r["date"][:10] <= cutoff]

        latest = self._get_latest_bar_time(code, 9)
        if latest:
            records = [r for r in records if r["date"] > latest]

        logging.debug(f"tencent {code}: {len(records)} new bars (cutoff={cutoff})")
        return records

    def save_klines(self, records: List[Dict[str, Any]]):
        if not records:
            return
        try:
            operations = []
            for record in records:
                operations.append(
                    UpdateOne(
                        {
                            "code": record["code"],
                            "date": record["date"],
                            "frequency": record["frequency"],
                        },
                        {"$set": record},
                        upsert=True,
                    )
                )
            result = self.storage.bulk_write(operations, ordered=False)
            saved_count = result.upserted_count + result.modified_count
            logging.debug(
                f"Saved {saved_count}/{len(records)} kline records for {records[0]['code']} "
                f"(upserted={result.upserted_count}, modified={result.modified_count})"
            )
        except Exception as e:
            logging.error(f"Failed to save klines: {e}")

    def fetch_daily_klines(self, codes: List[str] = None):
        if codes is None:
            codes = self._get_all_stock_codes()

        success = 0
        skipped = 0
        failed = 0

        for i, code in enumerate(codes):
            try:
                pure_code = code.split(".")[-1]
                records = self._fetch_kline(pure_code)
                if records is None:
                    failed += 1
                elif not records:
                    skipped += 1
                else:
                    self.save_klines(records)
                    success += 1

                if (i + 1) % 50 == 0:
                    logging.info(
                        f"Progress: {i + 1}/{len(codes)}, success={success}, skipped={skipped}, failed={failed}"
                    )
                time.sleep(0.15)

            except Exception as e:
                logging.error(f"Error processing {code}: {e}")
                logging.error(traceback.format_exc())
                failed += 1
                continue

        logging.info(
            f"Daily kline fetch completed: total={len(codes)}, success={success}, skipped={skipped}, failed={failed}"
        )
        return {"success": success, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    Log("kline_spider", log_type=Log.TYPE_FILE, level=logging.INFO)
    pid_file = os.path.join(home(), "apps", "api", "var", "run", "kline_spider.pid")
    single = ScriptSingle(pid_file)

    if single.is_running():
        logging.error("there is script lock {}".format(pid_file))
        sys.exit(0)
    spider = StockKlineScraper()
    klines = spider.fetch_daily_klines()
