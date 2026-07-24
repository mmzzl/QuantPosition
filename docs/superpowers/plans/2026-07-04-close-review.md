# 收盘分时复盘 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-of-day tick-by-tick review system that crawls 5-min K-line data for all A-shares, analyzes positions/vwap/volume/patterns for holdings + morning-recommended stocks, and pushes conclusions to DingTalk.

**Architecture:** Independent spider (`review_spider.py`) crawls all stocks after close → stores in `stock_kline_5m`. Independent runner (`review_runner.py`) queries target stocks, calls analysis engine (`review_service.py`), pushes DingTalk. Scheduled via `inputs.conf` cron.

**Tech Stack:** Python 3.12, MongoDB (pymongo), 腾讯 mkline API, APScheduler (inputs.conf)

---

### Task 1: 5-minute K-line spider — `bin/review_spider.py`

**Files:**
- Create: `apps/api/bin/review_spider.py`
- No test file needed (external API crawler)

- [ ] **Step 1: Create the spider script**

Create `apps/api/bin/review_spider.py`:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
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
            "https://web.ifzq.gtimg.cn/appstock/app/kline/mkline",
            params={"param": f"{market}{code},m5,,{count}"},
            timeout=10,
        )
        d = r.json()
    except Exception as e:
        logging.error(f"tencent HTTP error for {code}: {e}")
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
        time_str = str(bar[0]).strip()
        if not time_str:
            continue
        if not time_str.startswith(today_str):
            continue
        try:
            o, c, h, l = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
            v = int(float(bar[5])) if bar[5] else 0
            amt = float(bar[6]) if len(bar) > 6 and bar[6] else 0.0
        except (ValueError, TypeError):
            continue
        records.append({
            "code": code,
            "date": time_str,
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
```

- [ ] **Step 2: Verify the spider runs**

Run: `python apps/api/bin/review_spider.py`

Expected: Logs showing progress crawling stock codes.

---

### Task 2: Analysis engine — `services/review_service.py`

**Files:**
- Create: `apps/api/services/review_service.py`
- Create: `apps/api/tests/test_review_service.py`

- [ ] **Step 1: Write tests for position determination**

Create `apps/api/tests/test_review_service.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from datetime import datetime, timedelta
from services.review_service import ReviewService


def make_daily_kline(dates, closes, highs=None, lows=None, volumes=None):
    """Helper to create mock daily K-line data."""
    highs = highs or [c * 1.05 for c in closes]
    lows = lows or [c * 0.95 for c in closes]
    volumes = volumes or [100000] * len(closes)
    return [
        {
            "date": d,
            "open": closes[i],
            "close": closes[i],
            "high": highs[i],
            "low": lows[i],
            "volume": volumes[i],
        }
        for i, d in enumerate(dates)
    ]


class TestPositionDetermination:
    def test_high_position_stage_gain_over_40(self):
        closes = [10.0 * (1 + 0.03 * i) for i in range(20)]
        klines = make_daily_kline([f"2026-06-0{i+1:02d}" for i in range(20)], closes)
        assert ReviewService._determine_position(klines) == "高位"

    def test_mid_position_stage_gain_10_30(self):
        closes = [10.0 * (1 + 0.01 * i) for i in range(20)]
        klines = make_daily_kline([f"2026-06-0{i+1:02d}" for i in range(20)], closes)
        assert ReviewService._determine_position(klines) == "中段"

    def test_low_position_recent_breakout(self):
        closes = [5.0] * 15 + [5.5, 6.0, 6.5, 7.0, 7.5]
        klines = make_daily_kline([f"2026-06-0{i+1:02d}" for i in range(20)], closes)
        assert ReviewService._determine_position(klines) == "低位"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_review_service.py::TestPositionDetermination -v 2>&1`

Expected: `FAILED` — `ReviewService` not defined

- [ ] **Step 3: Implement position determination**

Create `apps/api/services/review_service.py`:

```python
from datetime import datetime
from typing import List, Dict, Any, Optional


class ReviewService:

    @staticmethod
    def _determine_position(daily_klines: List[Dict]) -> str:
        if len(daily_klines) < 5:
            return "中段"

        closes = [k["close"] for k in daily_klines]

        stage_gain = (closes[-1] - closes[0]) / closes[0]

        high_volume = max(k.get("volume", 0) for k in daily_klines[-10:])
        avg_volume = sum(k.get("volume", 0) for k in daily_klines[-10:]) / max(len(daily_klines[-10:]), 1)
        turnover_ratio = high_volume / avg_volume if avg_volume > 0 else 0

        if stage_gain > 0.40 or turnover_ratio > 3.0:
            return "高位"
        elif stage_gain > 0.10:
            return "中段"
        else:
            return "低位"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_review_service.py::TestPositionDetermination -v`

Expected: 3 passed

- [ ] **Step 5: Write tests for VWAP and price-vs-VWAP analysis**

Add to `tests/test_review_service.py`:

```python
class TestVWAPAnalysis:
    def make_5m_bars(self, times, closes, highs=None, lows=None, volumes=None):
        highs = highs or [c * 1.01 for c in closes]
        lows = lows or [c * 0.99 for c in closes]
        volumes = volumes or [10000] * len(closes)
        return [
            {
                "date": f"2026-07-04 {t}",
                "open": closes[i],
                "close": closes[i],
                "high": highs[i],
                "low": lows[i],
                "volume": volumes[i],
                "amount": volumes[i] * closes[i],
            }
            for i, t in enumerate(times)
        ]

    def test_strong_vwap_bars_above_line(self):
        times = [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]
        closes = [10.0 + i * 0.01 for i in range(len(times))]
        bars = self.make_5m_bars(times, closes)
        status, _ = ReviewService._analyze_vwap(bars)
        assert status == "强势"

    def test_weak_vwap_bars_below_line(self):
        times = [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]
        closes = [10.0 - i * 0.01 for i in range(len(times))]
        bars = self.make_5m_bars(times, closes)
        status, _ = ReviewService._analyze_vwap(bars)
        assert status == "弱势"

    def test_balanced_vwap_mixed(self):
        times = [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]
        closes = [10.0 + (0.02 if i % 2 == 0 else -0.02) for i in range(len(times))]
        bars = self.make_5m_bars(times, closes)
        status, _ = ReviewService._analyze_vwap(bars)
        assert status == "震荡"
```

- [ ] **Step 6: Run VWAP tests to verify they fail**

Run: `python -m pytest tests/test_review_service.py::TestVWAPAnalysis -v`

Expected: FAILED — `_analyze_vwap` not defined

- [ ] **Step 7: Implement VWAP analysis**

Add to `services/review_service.py`:

```python
    @staticmethod
    def _analyze_vwap(bars_5m: List[Dict]) -> tuple:
        if not bars_5m:
            return "震荡", 0

        total_pv = 0.0
        total_v = 0.0
        for bar in bars_5m:
            typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
            vol = bar["volume"]
            total_pv += typical_price * vol
            total_v += vol

        vwap = total_pv / total_v if total_v > 0 else bars_5m[-1]["close"]

        above_count = sum(1 for b in bars_5m if b["close"] >= vwap)
        ratio = above_count / len(bars_5m)

        first_half = bars_5m[:len(bars_5m)//2]
        second_half = bars_5m[len(bars_5m)//2:]
        vwap_first = sum(b["close"] for b in first_half) / len(first_half) if first_half else vwap
        vwap_second = sum(b["close"] for b in second_half) / len(second_half) if second_half else vwap
        vwap_slope = vwap_second - vwap_first

        if ratio >= 0.65 and vwap_slope > 0:
            return "强势", vwap
        elif ratio <= 0.35 and vwap_slope < 0:
            return "弱势", vwap
        else:
            return "震荡", vwap
```

- [ ] **Step 8: Run tests again**

Run: `python -m pytest tests/test_review_service.py::TestVWAPAnalysis -v`

Expected: 3 passed

- [ ] **Step 9: Write tests for volume analysis**

Add to `tests/test_review_service.py`:

```python
class TestVolumeAnalysis:
    def make_5m_bars(self, times, closes, volumes):
        return [
            {"date": f"2026-07-04 {t}", "open": c, "close": c, "high": c*1.01, "low": c*0.99, "volume": v, "amount": v*c}
            for t, c, v in zip(times, closes, volumes)
        ]

    def _gen_times(self):
        return [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]

    def test_distribution_signal_morning_spike_then_retreat(self):
        times = self._gen_times()
        closes = [10.0 + 0.1] * 3 + [9.9] * 3 + [9.85] * (len(times) - 6)
        volumes = [50000] * 3 + [5000] * 3 + [20000] * (len(times) - 6)
        bars = self.make_5m_bars(times, closes, volumes)
        signal, _ = ReviewService._analyze_volume(bars)
        assert signal == "出货"

    def test_suction_signal_down_low_vol_up_high_vol(self):
        times = self._gen_times()
        closes = [9.8] * 5 + [10.0] * 5 + [10.1] * (len(times) - 10)
        volumes = [3000] * 5 + [40000] * 5 + [35000] * (len(times) - 10)
        bars = self.make_5m_bars(times, closes, volumes)
        signal, _ = ReviewService._analyze_volume(bars)
        assert signal == "洗盘"

    def test_probe_signal_early_spike_then_quiet(self):
        times = self._gen_times()
        closes = [10.5] * 2 + [10.0] * (len(times) - 2)
        volumes = [60000] * 2 + [5000] * (len(times) - 2)
        bars = self.make_5m_bars(times, closes, volumes)
        signal, _ = ReviewService._analyze_volume(bars)
        assert signal == "试盘"
```

- [ ] **Step 10: Run volume tests to verify they fail**

Run: `python -m pytest tests/test_review_service.py::TestVolumeAnalysis -v`

Expected: FAILED — `_analyze_volume` not defined

- [ ] **Step 11: Implement volume analysis**

Add to `services/review_service.py`:

```python
    @staticmethod
    def _analyze_volume(bars_5m: List[Dict]) -> tuple:
        if len(bars_5m) < 10:
            return "震荡", "数据不足"

        segments = {
            "早盘": [b for b in bars_5m if b["date"][11:14] in ["09", "10"] and b["date"][11:16] <= "10:00"],
            "午盘": [b for b in bars_5m if "10:05" <= b["date"][11:16] <= "14:00"],
            "尾盘": [b for b in bars_5m if b["date"][11:16] >= "14:05"],
        }

        def avg_vol(bars):
            return sum(b["volume"] for b in bars) / max(len(bars), 1)

        def vol_trend(bars):
            if len(bars) < 4:
                return "平稳"
            half = len(bars) // 2
            first_avg = avg_vol(bars[:half])
            second_avg = avg_vol(bars[half:])
            if second_avg > first_avg * 1.5:
                return "放大"
            elif second_avg < first_avg * 0.5:
                return "萎缩"
            return "平稳"

        morning_vol = avg_vol(segments["早盘"])
        afternoon_vol = avg_vol(segments["午盘"])
        tail_vol = avg_vol(segments["尾盘"])
        tail_trend = vol_trend(segments["尾盘"])

        total_vol = sum(b["volume"] for b in bars_5m)
        up_vol = sum(b["volume"] for b in bars_5m if b["close"] >= b["open"])
        down_vol = total_vol - up_vol
        up_down_ratio = up_vol / max(down_vol, 1)

        first_bar = bars_5m[0]
        mid_bars = bars_5m[len(bars_5m)//3:2*len(bars_5m)//3]
        mid_max_close = max(b["close"] for b in mid_bars) if mid_bars else first_bar["close"]
        mid_max_vol = max(b["volume"] for b in mid_bars) if mid_bars else 0
        mid_max_bar = max(mid_bars, key=lambda b: b["volume"]) if mid_bars else None

        is_morning_spike = morning_vol > afternoon_vol * 2 and bars_5m[0]["close"] < bars_5m[min(3, len(bars_5m)-1)]["close"]
        second_peak_vol = max(b["volume"] for b in bars_5m[:8]) if len(bars_5m) >= 8 else 0
        has_retreat_volume = morning_vol > 0 and second_peak_vol < morning_vol * 0.5

        if is_morning_spike and has_retreat_volume:
            return "出货", "早盘放量急拉后缩量回落，量价背离"
        if up_down_ratio < 0.6 and tail_trend == "放大" and bars_5m[-1]["close"] < bars_5m[-1]["open"]:
            return "出货", "下跌放量，尾盘放量跳水"
        if up_down_ratio > 1.8 and tail_vol > morning_vol * 0.8 and bars_5m[-1]["close"] > bars_5m[-1]["open"]:
            return "洗盘", "下跌缩量上涨放量，尾盘放量拉升"
        if mid_max_vol > avg_vol(bars_5m) * 3 and mid_max_bar and mid_max_bar["close"] > first_bar["close"] * 1.03:
            return "试盘", "盘中突然大单拉升测试抛压"

        return "震荡", "无明显量价背离"
```

- [ ] **Step 12: Run volume tests**

Run: `python -m pytest tests/test_review_service.py::TestVolumeAnalysis -v`

Expected: 3 passed

- [ ] **Step 13: Write tests for pattern recognition**

Add to `tests/test_review_service.py`:

```python
class TestPatternRecognition:
    def _gen_times(self):
        return [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]

    def test_m_top_pattern(self):
        times = self._gen_times()
        closes = [10.0, 10.3, 10.25, 10.35, 10.3, 10.1, 10.0, 9.9, 9.85, 9.8
                 ] + [9.75] * (len(times) - 10)
        bars = [{"date": f"2026-07-04 {t}", "open": c, "close": c,
                 "high": c*1.02, "low": c*0.98, "volume": 10000, "amount": c*10000}
                for t, c in zip(times, closes)]
        pattern = ReviewService._recognize_pattern(bars, "弱势", "出货")
        assert pattern == "M头分时"

    def test_u_shape_pattern(self):
        times = self._gen_times()
        closes = [10.0, 9.8, 9.6, 9.5, 9.55, 9.7, 9.85, 10.0, 10.1, 10.15
                 ] + [10.2] * (len(times) - 10)
        bars = [{"date": f"2026-07-04 {t}", "open": c, "close": c,
                 "high": c*1.01, "low": c*0.99, "volume": 10000, "amount": c*10000}
                for t, c in zip(times, closes)]
        pattern = ReviewService._recognize_pattern(bars, "强势", "洗盘")
        assert pattern == "U型洗盘分时"

    def test_tail_accumulation_pattern(self):
        times = self._gen_times()
        closes = [10.0] * 30 + [10.1, 10.15, 10.2, 10.25, 10.3]
        volumes = [5000] * 30 + [30000, 35000, 40000, 45000, 50000]
        bars = [{"date": f"2026-07-04 {t}", "open": c, "close": c,
                 "high": c*1.01, "low": c*0.99, "volume": v, "amount": c*v}
                for t, c, v in zip(times, closes, volumes)]
        pattern = ReviewService._recognize_pattern(bars, "强势", "洗盘")
        assert pattern == "尾盘抢筹型"
```

- [ ] **Step 14: Run pattern tests to verify they fail**

Run: `python -m pytest tests/test_review_service.py::TestPatternRecognition -v`

Expected: FAILED

- [ ] **Step 15: Implement pattern recognition**

Add to `services/review_service.py`:

```python
    @staticmethod
    def _recognize_pattern(bars_5m: List[Dict], vwap_status: str, volume_signal: str) -> str:
        if len(bars_5m) < 20:
            return "震荡"

        closes = [b["close"] for b in bars_5m]
        highs = [b["high"] for b in bars_5m]
        first_half = closes[:len(closes)//2]
        second_half = closes[len(closes)//2:]

        avg_first = sum(first_half) / max(len(first_half), 1)
        avg_second = sum(second_half) / max(len(second_half), 1)
        mid_point = len(closes) // 2

        tail_bars = bars_5m[-6:]
        tail_vol_avg = sum(b["volume"] for b in tail_bars) / max(len(tail_bars), 1)
        overall_vol_avg = sum(b["volume"] for b in bars_5m) / max(len(bars_5m), 1)
        tail_price_rising = tail_bars[-1]["close"] > tail_bars[0]["close"] if tail_bars else False

        early_high = max(highs[:6]) if len(highs) >= 6 else 0
        second_peak = max(highs[3:9]) if len(highs) >= 9 else 0
        has_double_top = early_high > 0 and second_peak > 0 and abs(early_high - second_peak) / max(early_high, 0.01) < 0.03

        if vwap_status == "弱势" and volume_signal == "出货":
            if has_double_top:
                return "M头分时"
            if closes[0] > closes[-1] and closes[0] > closes[len(closes)//4] * 1.02:
                return "高开低走阴跌型"
            if bars_5m[0]["close"] < bars_5m[min(2, len(bars_5m)-1)]["close"] and closes[-1] < closes[0]:
                return "早盘脉冲全天回落"

        if volume_signal == "洗盘":
            if avg_second > avg_first and closes[-1] > closes[0]:
                return "U型洗盘分时"
            if avg_second >= avg_first * 1.01 and closes[-1] > closes[0]:
                return "单边震荡上行"

        if tail_vol_avg > overall_vol_avg * 1.5 and tail_price_rising:
            return "尾盘抢筹型"

        if has_double_top:
            return "M头分时"

        return "震荡平衡形态"
```

- [ ] **Step 16: Run pattern tests**

Run: `python -m pytest tests/test_review_service.py::TestPatternRecognition -v`

Expected: 3 passed

- [ ] **Step 17: Write tests for conclusion generation**

Add to `tests/test_review_service.py`:

```python
class TestConclusion:
    def test_sell_conclusion_high_weak_distribution(self):
        result = ReviewService._generate_conclusion(
            position="高位", vwap_status="弱势",
            volume_signal="出货", pattern="M头分时",
            tail_signal="放量跳水"
        )
        assert result["conclusion"] == "卖出"

    def test_hold_conclusion_mid_strong_suction(self):
        result = ReviewService._generate_conclusion(
            position="中段", vwap_status="强势",
            volume_signal="洗盘", pattern="U型洗盘分时",
            tail_signal="抢筹"
        )
        assert result["conclusion"] == "持有"

    def test_watch_conclusion(self):
        result = ReviewService._generate_conclusion(
            position="中段", vwap_status="震荡",
            volume_signal="震荡", pattern="震荡平衡形态",
            tail_signal="无量横盘"
        )
        assert result["conclusion"] == "观望"
```

- [ ] **Step 18: Run conclusion tests to verify they fail**

Run: `python -m pytest tests/test_review_service.py::TestConclusion -v`

Expected: FAILED

- [ ] **Step 19: Implement conclusion generation**

Add to `services/review_service.py`:

```python
    @staticmethod
    def _generate_conclusion(position: str, vwap_status: str, volume_signal: str,
                             pattern: str, tail_signal: str) -> Dict[str, str]:
        sell_signals = 0

        if position == "高位":
            sell_signals += 1
        if vwap_status == "弱势":
            sell_signals += 1
        if volume_signal == "出货":
            sell_signals += 1
        if pattern in ("M头分时", "高开低走阴跌型", "早盘脉冲全天回落"):
            sell_signals += 1

        if tail_signal == "放量跳水":
            sell_signals += 1

        hold_conditions = (
            position in ("低位", "中段")
            and vwap_status == "强势"
            and volume_signal == "洗盘"
            and pattern in ("U型洗盘分时", "单边震荡上行", "尾盘抢筹型")
        )

        if hold_conditions:
            return {
                "conclusion": "持有",
                "reason": f"{position}启动+均价支撑+下跌缩量上涨放量+尾盘稳定",
                "strategy": "次日只要不有效跌破均价，全程持有，等冲高放量滞涨再分批卖出",
            }

        if sell_signals >= 2:
            return {
                "conclusion": "卖出",
                "reason": f"{' '.join([('高位' if position=='高位' else ''), ('均价弱势' if vwap_status=='弱势' else ''), ('量价背离' if volume_signal=='出货' else ''), (pattern if pattern!='震荡平衡形态' else '')])}",
                "strategy": "次日开盘不抱有幻想，小幅冲高即全部卖出，规避日内大跌",
            }

        return {
            "conclusion": "观望",
            "reason": "多空分歧，无明显方向信号",
            "strategy": "次日减半仓观望，等方向明确后再操作",
        }
```

- [ ] **Step 20: Run conclusion tests**

Run: `python -m pytest tests/test_review_service.py::TestConclusion -v`

Expected: 3 passed

- [ ] **Step 21: Write tests for the main analyze method**

Add to `tests/test_review_service.py`:

```python
class TestAnalyze:
    def test_analyze_returns_structured_result(self, monkeypatch):
        def mock_daily(code):
            closes = [10.0 * (1 + 0.02 * i) for i in range(20)]
            return [{"date": f"2026-06-0{i+1:02d}", "open": c, "close": c,
                     "high": c*1.03, "low": c*0.97, "volume": 100000}
                    for i, c in enumerate(closes)]

        def mock_5m(code, date_str):
            times = [f"{h:02d}:{m:02d}" for h in range(9, 15) for m in [35, 40, 45, 50, 55]]
            closes = [10.0 + i * 0.005 for i in range(len(times))]
            return [{"date": f"{date_str} {t}", "open": c, "close": c,
                     "high": c*1.01, "low": c*0.99, "volume": 10000, "amount": c*10000}
                    for t, c in zip(times, closes)]

        monkeypatch.setattr(ReviewService, "_get_daily_klines", staticmethod(lambda code, days: mock_daily(code)))
        monkeypatch.setattr(ReviewService, "_get_5m_klines", staticmethod(lambda code, d: mock_5m(code, d)))

        result = ReviewService.analyze("600000", "浦发银行", "2026-07-04")
        assert result["code"] == "600000"
        assert result["name"] == "浦发银行"
        assert result["conclusion"] in ("持有", "卖出", "观望")
        assert "position" in result
        assert "vwap_status" in result
        assert "volume_signal" in result
        assert "pattern" in result
```

- [ ] **Step 22: Implement main analyze method**

Add to `services/review_service.py`:

```python
    @staticmethod
    def _get_daily_klines(code: str, days: int = 60) -> List[Dict]:
        from database import get_db
        from datetime import timedelta
        db = get_db()
        now = datetime.now()
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d") + " 23:59"
        return list(db.stock_kline.find({
            "code": code,
            "frequency": 9,
            "date": {"$gte": start, "$lte": end}
        }).sort("date", 1))

    @staticmethod
    def _get_5m_klines(code: str, date_str: str) -> List[Dict]:
        from database import get_db
        db = get_db()
        return list(db.stock_kline_5m.find({
            "code": code,
            "date": {"$regex": f"^{date_str}"}
        }).sort("date", 1))

    @staticmethod
    def analyze(code: str, name: str, date_str: str = None) -> Dict[str, Any]:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        daily_klines = ReviewService._get_daily_klines(code)
        bars_5m = ReviewService._get_5m_klines(code, date_str)

        if not bars_5m:
            return {"code": code, "name": name, "conclusion": "跳过", "reason": f"{date_str} 无 5 分钟 K 线数据"}

        position = ReviewService._determine_position(daily_klines)
        vwap_status, vwap = ReviewService._analyze_vwap(bars_5m)
        volume_signal, vol_detail = ReviewService._analyze_volume(bars_5m)
        pattern = ReviewService._recognize_pattern(bars_5m, vwap_status, volume_signal)

        tail_bars = bars_5m[-6:]
        tail_vol = sum(b["volume"] for b in tail_bars)
        overall_avg_vol = sum(b["volume"] for b in bars_5m) / max(len(bars_5m), 1)
        if tail_vol > len(tail_bars) * overall_avg_vol * 1.5 and tail_bars[-1]["close"] > tail_bars[0]["close"]:
            tail_signal = "抢筹"
        elif tail_vol > len(tail_bars) * overall_avg_vol * 1.5 and tail_bars[-1]["close"] < tail_bars[0]["close"]:
            tail_signal = "放量跳水"
        else:
            tail_signal = "无量横盘"

        conclusion = ReviewService._generate_conclusion(position, vwap_status, volume_signal, pattern, tail_signal)

        return {
            "code": code,
            "name": name,
            "date": date_str,
            "position": position,
            "vwap_status": vwap_status,
            "volume_signal": volume_signal,
            "volume_detail": vol_detail,
            "pattern": pattern,
            "tail_signal": tail_signal,
            "conclusion": conclusion["conclusion"],
            "reason": conclusion["reason"],
            "strategy": conclusion["strategy"],
        }
```

- [ ] **Step 23: Run all review_service tests**

Run: `python -m pytest tests/test_review_service.py -v`

Expected: All tests pass

---

### Task 3: Runner script — `bin/review_runner.py`

**Files:**
- Create: `apps/api/bin/review_runner.py`

- [ ] **Step 1: Create the runner script**

Create `apps/api/bin/review_runner.py`:

```python
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

        emoji_map = {"卖出": "🔴", "持有": "🟢", "观望": "🟡"}
        icon = emoji_map.get(r["conclusion"], "⚪")
        vwap_icon = "✅" if r["vwap_status"] == "强势" else ("❌" if r["vwap_status"] == "弱势" else "➖")
        tail_icon = "✅" if r["tail_signal"] == "抢筹" else ("❌" if r["tail_signal"] == "放量跳水" else "➖")

        lines.append(f"━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{icon} **{r['code']} {r['name']}**")
        lines.append(f"📌 日线定位：{r['position']}")
        lines.append(f"📈 均价分析：{r['vwap_status']} {vwap_icon}")
        lines.append(f"📊 量能分析：{r['volume_signal']}")
        lines.append(f"🔍 分时形态：{r['pattern']}")
        lines.append(f"🌙 尾盘信号：{r['tail_signal']} {tail_icon}")
        lines.append(f"🎯 **结论：{r['conclusion']}**")
        lines.append(f"💡 {r['strategy']}")

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
            logging.info(f"分析完成: {t['code']} {t['name']} → {result['conclusion']}")
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
```

- [ ] **Step 2: Verify runner can import**

Run: `python -c "import sys; sys.path.insert(0, 'apps/api'); from services.review_service import ReviewService; print('OK')"`

Expected: `OK`

---

### Task 4: Update scheduler config — `config/inputs.conf`

**Files:**
- Modify: `apps/api/config/inputs.conf`

- [ ] **Step 1: Add crawler and runner cron tasks**

Edit `apps/api/config/inputs.conf`, append these lines:

```ini
[script://bin/review_spider.py]
enable = true
cron=hour=16,minute=0,day_of_week=0-4

[script://bin/review_runner.py]
enable = true
cron=hour=16,minute=15,day_of_week=0-4
```

- [ ] **Step 2: Verify config syntax**

Read the file and confirm the new entries match the existing format.

---

### Task 5: Integration verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/test_review_service.py -v`

Expected: All tests pass

- [ ] **Step 2: Verify imports work end-to-end**

Run: `python -c "
import sys; sys.path.insert(0, 'apps/api')
from services.review_service import ReviewService
from bin.review_spider import MinuteKlineScraper
print('All imports OK')
"`

Expected: `All imports OK`
