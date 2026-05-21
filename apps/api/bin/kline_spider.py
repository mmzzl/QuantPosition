import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import traceback
import socket
import pandas as pd
import logging

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from mootdx.quotes import Quotes
from mootdx import config
from pymongo import UpdateOne

from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home
from database import get_db


BATCH_SIZE = 800

HQ_HOSTS = [
    ("深圳双线主站1", "110.41.147.114", 7709),
    ("深圳双线主站2", "8.129.13.54", 7709),
    ("上海双线主站1", "124.70.176.52", 7709),
    ("上海双线主站2", "47.100.236.28", 7709),
    ("北京双线主站1", "121.36.54.217", 7709),
    ("北京双线主站2", "121.36.81.195", 7709),
    ("广州双线主站1", "124.71.85.110", 7709),
    ("广州双线主站2", "139.9.51.18", 7709),
    ("武汉电信主站1", "119.97.185.59", 7709),
    ("深圳双线主站7", "47.107.64.168", 7709),
    ("上海双线主站15", "123.60.84.66", 7709),
]


def _test_server(ip: str, port: int, timeout: float = 3.0) -> bool:
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _find_working_server() -> tuple:
    for name, ip, port in HQ_HOSTS:
        logging.info(f"Testing server: {name} ({ip}:{port})")
        if _test_server(ip, port):
            logging.info(f"Server OK: {name} ({ip}:{port})")
            return (ip, port)
    raise ConnectionError("All HQ servers are unreachable")


class StockKlineScraper:
    def __init__(self):
        self.storage = get_db()['stock_kline']
        self.client = self._create_client()
        self._qlib_sync_pending: Dict[str, bool] = {}
        self._qlib_defer_sync = False

    def _create_client(self):
        config.setup()
        bestip = config.get("BESTIP", {}).get("HQ")
        candidates = [bestip] if bestip else []

        if not candidates:
            for _, ip, port in HQ_HOSTS:
                candidates.append((ip, port))

        last_error = None
        for ip, port in candidates:
            try:
                logging.info(f"Connecting to HQ server {ip}:{port}")
                client = Quotes.factory(
                    market="std",
                    multithread=True,
                    heartbeat=False,
                    server=(ip, port),
                    timeout=15,
                )
                config.set("BESTIP", {"HQ": (ip, port)})
                logging.info(f"Connected to HQ server {ip}:{port}")
                return client
            except Exception as e:
                logging.warning(f"Failed to connect {ip}:{port}: {e}")
                last_error = e
                continue

        logging.warning("All cached servers failed, trying full server scan...")
        ip, port = _find_working_server()
        client = Quotes.factory(
            market="std",
            multithread=True,
            heartbeat=False,
            server=(ip, port),
            timeout=15,
        )
        config.set("BESTIP", {"HQ": (ip, port)})
        logging.info(f"Connected to HQ server {ip}:{port}")
        return client

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass

    def _get_latest_bar_time(self, code: str,frequency: int) -> Optional[str]:
        """获取某只股票最新一条 K 线的时间戳"""
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
        """从 data/all_stock.csv 加载股票代码"""
        codes = set()
        path = os.path.join(home(), "apps", "api", "data", "all_stock.csv")
        try:
            df = pd.read_csv(path)
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                if code:
                    # "sh.000001" -> "000001"
                    pure = code.split(".")[-1]
                    if pure.isdigit():
                        codes.add(pure)
            logging.info(f"Loaded {len(codes)} stock codes from all_stock.csv")
        except Exception as e:
            logging.error(f"Failed to load all_stock.csv: {e}")
            raise

        return sorted(list(codes))

    def _fetch_kline(
        self,
        code: str,
        frequency: int = 9,
        start: int = 0,
        count: int = BATCH_SIZE,
        adjust: str = "qfq",
    ) -> List[Dict[str, Any]]:
        for attempt in range(2):
            try:
                df = self.client.bars(
                    symbol=code,
                    freq=frequency,
                    start=start,
                    offset=count,
                )
                if df is None or df.empty:
                    return []

                if isinstance(df.columns, pd.RangeIndex):
                    df.columns = ["date", "open", "high", "low", "close", "amount", "volume"]
                else:
                    column_map = {
                        "datetime": "date",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "amount": "amount",
                        "volume": "volume",
                    }
                    available_cols = [c for c in column_map.keys() if c in df.columns]
                    df = df[available_cols].rename(columns=column_map)

                records = []
                for _, row in df.iterrows():
                    try:
                        records.append(
                            {
                                "code": code,
                                "date": str(row["date"]),
                                "open": float(row["open"]),
                                "high": float(row["high"]),
                                "low": float(row["low"]),
                                "close": float(row["close"]),
                                "volume": int(row["volume"])
                                if pd.notna(row["volume"])
                                else 0,
                                "amount": float(row["amount"])
                                if pd.notna(row["amount"])
                                else 0.0,
                                "frequency": frequency,
                                "adjust": adjust,
                                "crawl_time": datetime.now().isoformat(),
                            }
                        )
                    except (ValueError, TypeError, KeyError) as e:
                        logging.error(f"Parse error for {code}: {e}")
                        continue
                if frequency == 0 and len(records) <= 2:
                    logging.debug(f"mootdx returned only {len(records)} bars for {code} freq={frequency}")
                return records
            except Exception as e:
                logging.error(f"Failed to fetch kline for {code} (attempt {attempt + 1}): {e}")
                if attempt == 0:
                    logging.warning("Reconnecting before retry...")
                    try:
                        self.client.close()
                    except Exception:
                        pass
                    self.client = self._create_client()
                continue
        return []

    def _need_fetch(self, code: str, frequency: int = 9) -> bool:
        today = "%s 15:00" % datetime.now().strftime("%Y-%m-%d")
        try:
            doc = self.storage.find_one(
                {"code": code, "date": today}
            )
            return doc is None
        except Exception as e:
            logging.warning(f"Failed to check existence for {code}: {e}")
            return True

    def _get_fetch_count(self, code: str, frequency: int) -> int:
        """根据最后同步日期计算需要拉取的K线条数

        取MongoDB中该股票最新一根K线的日期，与今天相减，
        估算缺失交易日天数作为 count（加 buffer 确保覆盖）。
        首次同步（无数据）返回 BATCH_SIZE。
        """
        latest = self._get_latest_bar_time(code, frequency)
        if not latest:
            return BATCH_SIZE

        try:
            last_date = datetime.strptime(latest[:10], "%Y-%m-%d").date()
            diff = (datetime.now().date() - last_date).days
            if diff <= 0:
                return 0  # 已包含今日数据
            if frequency == 0:
                # 5分钟线：每个交易日约48根，加buffer
                return max(int(diff * 60), BATCH_SIZE)
            # 日线：交易日约占总天数70%，乘2保证覆盖
            return max(int(diff * 2), 1)
        except ValueError:
            return BATCH_SIZE

    def save_klines(self, records: List[Dict[str, Any]], frequency: int = 9):
        if not records:
            return
        
        try:
            operations = []
            for record in records:
                record_frequency = record.get("frequency", frequency)
                operations.append(
                    UpdateOne(
                        {"code": record["code"], "date": record["date"], "frequency": record_frequency},
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
            

    def fetch_daily_klines(
        self,
        codes: List[str] = None,
        adjust: str = "qfq",
    ):
        """增量获取日K线：每只股票只取最新一批数据，不做历史全量拉取

        Parameters
        ----------
        codes : List[str], optional
            股票代码列表，不指定则自动获取
        adjust : str, default "qfq"
            复权类型
        """
        if codes is None:
            codes = self._get_all_stock_codes()

        frequency = 9
        success = 0
        skipped = 0
        failed = 0

        for i, code in enumerate(codes):
            try:
                pure_code = code.split(".")[-1]

                count = self._get_fetch_count(pure_code, frequency)
                if count > 0:
                    records = self._fetch_kline(
                        pure_code,
                        frequency=frequency,
                        start=0,
                        count=count,
                        adjust=adjust,
                    )
                    if records:
                        self.save_klines(records, frequency=frequency)
                        success += 1
                    else:
                        failed += 1
                else:
                    skipped += 1

                if (i + 1) % 50 == 0:
                    logging.info(
                        f"Progress: {i + 1}/{len(codes)}, success={success}, skipped={skipped}, failed={failed}"
                    )

                time.sleep(0.1)

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
    pid_file = os.path.join(home(), 'apps', 'api', 'var', 'run', 'kline_spider.pid')
    single = ScriptSingle(pid_file)

    if single.is_running():
        logging.error('there is script lock {}'.format(pid_file))
        sys.exit(0)
    spider = StockKlineScraper()
    klines = spider.fetch_daily_klines()