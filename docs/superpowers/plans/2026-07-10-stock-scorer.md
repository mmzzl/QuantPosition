# 统一短线评分系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified StockScorer module (0-100) for the entire project — daily kline-based price-volume scoring + akshare-based fund flow/chip/sector scoring + risk check. Replace the existing ad-hoc scoring in review_picker, rule_engine, and backtest_engine.

**Architecture:** `StockScorer.score(code, name, date_str)` aggregates 4 independent sub-modules: `price_volume` (40pts, pure local), `fund_chip` (35pts, akshare batch+single), `sector_theme` (20pts, akshare batch), `risk_check` (5pts, local). Each sub-module returns `{total: int, breakdown: dict}`. Akshare calls are cached per-run with a simple dict cache.

**Tech Stack:** Python 3.12, MongoDB (pymongo), akshare (同花顺/新浪/东方财富), existing daily klines in `stock_kline`

---

### Task 1: Package structure + `__init__`

**Files:**
- Create: `apps/api/services/scorer/__init__.py`

- [ ] **Step 1: Create package init**

```python
# apps/api/services/scorer/__init__.py
```

Empty file (package marker only).

- [ ] **Step 2: Commit**

```bash
git add apps/api/services/scorer/__init__.py
git commit -m "feat: create scorer package"
```

---

### Task 2: `price_volume.py` — 量价趋势评分 (40分)

**Files:**
- Create: `apps/api/services/scorer/price_volume.py`
- Create: `apps/api/tests/scorer/test_price_volume.py`

**Logic overview:**

Daily klines are sorted by date DESC, most recent first. The input is a list of dicts with keys: `code, date, open, close, high, low, volume`.

MA5 = average close of most recent 5 entries, MA10 = average close of most recent 10 entries, MA20 = average close of most recent 20 entries.

`stage_gain` = (current_close - close_of_20_days_ago) / close_of_20_days_ago * 100.

Volume average = average of last 5 entries' volume.

Amplitude = (high - low) / close of each day, averaged over last 5 days.

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/scorer/test_price_volume.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.scorer.price_volume import score_price_volume


def _kline(close, volume, high=None, low=None, date=None):
    return {
        "close": close,
        "volume": volume,
        "high": high or close * 1.02,
        "low": low or close * 0.98,
        "date": date or "2026-07-10",
    }


def _klines(closes, volumes, dates=None):
    dates = dates or [f"2026-07-{10-i:02d}" for i in range(len(closes))]
    highs = [c * 1.02 for c in closes]
    lows = [c * 0.98 for c in closes]
    return [
        {"close": c, "volume": v, "high": h, "low": l, "date": d}
        for c, v, h, l, d in zip(closes, volumes, highs, lows, dates)
    ]


def test_empty_klines():
    result = score_price_volume([], "2026-07-10")
    assert result["total"] == 0


def test_ma_bullish_and_above_ma5():
    # close=11,10,9,8,7 — MA5=9, MA10 trending, MA20 trending
    klines = _klines(
        closes=[11, 10.5, 10, 9.5, 9, 8.5, 8, 7.5, 7, 6.5, 6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5],
        volumes=[100]*20,
    )
    # MA5 = (11+10.5+10+9.5+9)/5 = 10.0
    # MA10 = (11+10.5+10+9.5+9+8.5+8+7.5+7+6.5)/10 = 8.75
    # MA20 = average of all = 6.5
    # close=11 > MA5=10, MA5=10 > MA10=8.75, MA10=8.75 > MA20=6.5 → bullish
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["ma_trend"] == 15, f"Expected 15, got {result['breakdown']['ma_trend']}"


def test_volume_price_healthy():
    # Most recent 3 days: volume > avg×1.2, close rising, max_retracement_day volume < avg
    klines = _klines(
        closes=[12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5],
        volumes=[200, 150, 80, 180, 200, 220, 100, 90],
    )
    # avg volume of last 5 = (200+150+80+180+200)/5 = 162
    # today vol=200 > 162*1.2=194.4? 200>194.5 → yes 4pts
    # today close=12 > 3days ago close=10 → yes 4pts
    # max retracement day among last 3 (closes: 12,11.5,11 → 11.5 is a retracement from 12)
    # volume on retracement day (index 1) = 150 < 162 → yes 4pts
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["volume_price"] >= 8


def test_breakthrough_20day_high():
    closes = [10]*19 + [12]
    volumes = [100]*20
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["breakthrough"] == 8


def test_breakthrough_10day_high_only():
    closes = [10]*9 + [12] + [10]*10
    volumes = [100]*20
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["breakthrough"] == 4


def test_amplitude_moderate():
    # 5% avg amplitude → 5pts
    klines = _klines(
        closes=[10]*20,
        volumes=[100]*20,
    )
    result = score_price_volume(klines, "2026-07-10")
    # amplitude = (10*1.02 - 10*0.98) / 10 = 0.04 → 4% → 3pts
    assert result["breakdown"]["amplitude"] >= 0


def test_penalty_below_ma20():
    # close < MA20 → total = 0
    closes = [10]*19 + [5]  # close=5, MA20 ~ 9.75
    volumes = [100]*20
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] == 0


def test_penalty_consecutive_drop():
    # 3 days loss > 5% total, each day volume > avg×1.5
    closes = [10, 10.5, 9.5, 9.0, 8.5]  # last 3: 10→9.5→9.0→8.5 = drop ~15%
    volumes = [100, 300, 280, 310, 100]  # days 3,4,5: vol > avg×1.5
    klines = _klines(closes[-20:] if len(closes)<20 else closes, volumes[-20:] if len(volumes)<20 else volumes)
    # pad to 20
    closes_full = [10]*15 + closes
    volumes_full = [100]*15 + volumes
    klines = _klines(closes_full, volumes_full)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] == 0


def test_penalty_high_position_stagnation():
    # stage_gain > 30%, volume > avg×1.3, gain < 0.5%
    closes = [7]*19 + [10]  # gain = (10-7)/7 = 42.8% > 30%
    volumes = [100]*19 + [300]  # vol=300 > 100*1.3=130
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] == 0


def test_full_score_conditions():
    # Best case: all conditions met
    closes = []
    c = 10.0
    for i in range(20):
        c = c * 1.02  # 2% upward trend
        closes.append(round(c, 2))
    volumes = [round(200 * (1.1 if i < 3 else 1.0), 0) for i in range(20)]
    # Most recent 3 have high volume, day3 ago had low volume (retracement)
    volumes[-1] = 250
    volumes[-2] = 240
    volumes[-3] = 80  # retracement day - low volume
    volumes[-4] = 230
    volumes[-5] = 220
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["total"] >= 30  # should be well above 0


def test_amplitude_too_low():
    # < 2% → 0pts
    klines = _klines(
        closes=[10]*20,
        volumes=[100]*20,
    )
    # Override highs/lows to be very tight
    for k in klines:
        k["high"] = k["close"] * 1.005
        k["low"] = k["close"] * 0.995
    result = score_price_volume(klines, "2026-07-10")
    # amplitude = 0.01 = 1% → 0pts
    assert result["breakdown"]["amplitude"] == 0


def test_volume_retracement_not_shrinking():
    # retracement day volume NOT below avg → loss of 4pts
    closes = [12, 11.5, 11, 10.5, 10]
    volumes = [200, 200, 200, 200, 100]
    klines = _klines(closes, volumes)
    result = score_price_volume(klines, "2026-07-10")
    assert result["breakdown"]["volume_price"] < 12  # should lose the retracement 4pts


def test_full_score_breakdown_keys():
    klines = _klines([10]*20, [100]*20)
    result = score_price_volume(klines, "2026-07-10")
    assert "total" in result
    assert "breakdown" in result
    for key in ("ma_trend", "volume_price", "breakthrough", "amplitude"):
        assert key in result["breakdown"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/api/tests/scorer/test_price_volume.py -v`
Expected: FAIL with `ModuleNotFoundError` for each test

- [ ] **Step 3: Write minimal implementation**

```python
# apps/api/services/scorer/price_volume.py
"""量价趋势评分 (40分)"""
import logging
from typing import List, Dict, Any


def score_price_volume(klines: List[Dict], date_str: str) -> Dict[str, Any]:
    if not klines or len(klines) < 5:
        return {"total": 0, "breakdown": {"ma_trend": 0, "volume_price": 0, "breakthrough": 0, "amplitude": 0}}

    # Sort by date descending, most recent first
    sorted_k = sorted(klines, key=lambda x: x["date"], reverse=True)

    def ma(n):
        vals = [k["close"] for k in sorted_k[:n] if k["close"]]
        return sum(vals) / len(vals) if vals else 0

    def vol_avg(n):
        vals = [k["volume"] for k in sorted_k[:n] if k["volume"]]
        return sum(vals) / len(vals) if vals else 0

    today = sorted_k[0]
    close = today["close"]
    ma5 = ma(5)
    ma10 = ma(10)
    ma20 = ma(20)
    vol5 = vol_avg(5)

    # 1.1 MA trend (15pts)
    ma_trend = 0
    if ma5 > ma10 > ma20 and close > ma5:
        ma_trend = 15
    elif close > ma5:
        ma_trend = 5 + (5 if ma5 > ma10 else 0)
    elif close > ma10 and ma10 > ma20:
        ma_trend = 2

    # 1.2 Volume-price (12pts)
    volume_price = 0
    if len(sorted_k) >= 3:
        day3_ago = sorted_k[3]["close"] if len(sorted_k) > 3 else sorted_k[-1]["close"]
        if close > day3_ago:
            volume_price += 4
        if vol5 > 0 and today["volume"] > vol5 * 1.2:
            volume_price += 4
        # Check if retracement days in last 3 had lower volume
        last_3_closes = [k["close"] for k in sorted_k[:3]]
        if len(last_3_closes) >= 3:
            max_c = max(last_3_closes)
            retracement_volumes = []
            for i in range(1, 3):
                if sorted_k[i]["close"] < sorted_k[i-1]["close"]:
                    retracement_volumes.append(sorted_k[i]["volume"])
            if retracement_volumes and all(v < vol5 for v in retracement_volumes):
                volume_price += 4

    # 1.3 Breakthrough (8pts)
    breakthrough = 0
    if len(sorted_k) >= 20:
        high_20 = max(k["high"] for k in sorted_k[:20])
        if close >= high_20:
            breakthrough = 8
        elif len(sorted_k) >= 10:
            high_10 = max(k["high"] for k in sorted_k[:10])
            if close >= high_10:
                breakthrough = 4
    elif len(sorted_k) >= 10:
        high_10 = max(k["high"] for k in sorted_k[:10])
        if close >= high_10:
            breakthrough = 4

    # 1.4 Amplitude (5pts)
    amplitude = 0
    amp_vals = []
    for k in sorted_k[:5]:
        if k.get("high") and k.get("low") and k["close"]:
            amp = (k["high"] - k["low"]) / k["close"]
            amp_vals.append(amp)
    if amp_vals:
        avg_amp = sum(amp_vals) / len(amp_vals)
        if 0.03 <= avg_amp <= 0.08:
            amplitude = 5
        elif (0.02 <= avg_amp < 0.03) or (0.08 < avg_amp <= 0.12):
            amplitude = 3

    total = ma_trend + volume_price + breakthrough + amplitude

    # Penalty — check if total should be zeroed
    if len(sorted_k) >= 3 and ma20 > 0 and close < ma20:
        total = 0
    elif len(sorted_k) >= 4:
        # consecutive large-volume drop
        recent_3 = sorted_k[:3]
        total_drop_pct = (recent_3[0]["close"] - recent_3[2]["close"]) / recent_3[2]["close"]
        if total_drop_pct < -0.05 and vol5 > 0:
            if all(k["volume"] > vol5 * 1.5 for k in recent_3):
                total = 0
    # High position stagnation
    if len(sorted_k) >= 20 and ma20 > 0 and total > 0:
        price_20d_ago = sorted_k[19]["close"]
        stage_gain = (close - price_20d_ago) / price_20d_ago
        if stage_gain > 0.30 and vol5 > 0 and today["volume"] > vol5 * 1.3:
            if len(sorted_k) >= 2:
                gain_today = (close - sorted_k[1]["close"]) / sorted_k[1]["close"]
                if gain_today < 0.005:
                    total = 0

    return {
        "total": min(total, 40),
        "breakdown": {
            "ma_trend": ma_trend,
            "volume_price": volume_price,
            "breakthrough": breakthrough,
            "amplitude": amplitude,
        },
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest apps/api/tests/scorer/test_price_volume.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add apps/api/services/scorer/price_volume.py apps/api/tests/scorer/test_price_volume.py
git commit -m "feat: add price_volume scoring module"
```

---

### Task 3: `fund_chip.py` — 资金筹码评分 (35分)

**Files:**
- Create: `apps/api/services/scorer/fund_chip.py`
- Create: `apps/api/tests/scorer/test_fund_chip.py`

Dependencies: akshare (同花顺 `stock_fund_flow_individual`, 新浪 `stock_lhb_detail_daily_sina`, 东方财富 `stock_cyq_em`). All wrapped in try/except.

**Cache strategy:** Module-level dict cache storing batch results keyed by date.

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/scorer/test_fund_chip.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch, MagicMock
import pandas as pd

from services.scorer.fund_chip import score_fund_chip, _cache, clear_cache


def setup_function():
    clear_cache()


def _mock_fund_flow_df(code, net_amount=100_000_000, rank=100):
    """Mock return of stock_fund_flow_individual('3日排行')"""
    data = {
        "股票代码": [code],
        "股票简称": ["TestStock"],
        "最新价": [10.0],
        "涨跌幅": [2.5],
        "换手率": [8.0],
        "净额": [net_amount],
    }
    return pd.DataFrame(data)


def _mock_lhb_df(code, net_buy=50_000_000):
    """Mock return of stock_lhb_detail_daily_sina"""
    data = {
        "股票代码": [code],
        "股票名称": ["TestStock"],
        "收盘价": [10.0],
        "对应值(%)": [2.5],
        "成交量(万股)": [100],
        "成交额(万元)": [1000],
        "指标": ["机构买入"],
    }
    return pd.DataFrame(data)


def _mock_cyq_df(concentration=8.0):
    """Mock return of stock_cyq_em"""
    data = {
        "日期": ["2026-07-10"],
        "获利比例": [60.0],
        "平均成本": [10.0],
        "90成本-低": [9.0],
        "90成本-高": [11.0],
        "90集中度": [concentration],
        "70成本-低": [9.5],
        "70成本-高": [10.5],
        "70集中度": [concentration * 0.8],
    }
    return pd.DataFrame(data)


def test_fund_flow_strong():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", net_amount=500_000_000, rank=50)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001", net_buy=50_000_000)
        mock_ak.stock_cyq_em.return_value = _mock_cyq_df(concentration=5.0)
        # Turnover 8% → 5pts
        result = score_fund_chip("000001", "2026-07-10", turnover_pct=8.0)
    assert result["breakdown"]["fund_flow"] == 12
    assert result["breakdown"]["lhb"] == 10
    assert result["breakdown"]["chip"] == 8
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 35


def test_fund_flow_negative():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", net_amount=-50_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001", net_buy=-10_000_000)
        mock_ak.stock_cyq_em.return_value = _mock_cyq_df(concentration=25.0)
        result = score_fund_chip("000001", "2026-07-10", turnover_pct=2.0)
    assert result["breakdown"]["fund_flow"] == 0  # negative net → 0
    assert result["breakdown"]["lhb"] == 0  # negative net buy
    assert result["breakdown"]["chip"] == 2  # concentration > 20% → 2
    assert result["breakdown"]["turnover"] == 0  # < 3% → 0
    assert result["total"] == 2


def test_fund_flow_not_in_rank():
    """Stock not in top 500 but has positive net flow"""
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", net_amount=50_000_000, rank=600)
        mock_ak.stock_lhb_detail_daily_sina.return_value = pd.DataFrame()  # not on LHB
        mock_ak.stock_cyq_em.return_value = _mock_cyq_df(concentration=15.0)
        result = score_fund_chip("000001", "2026-07-10", turnover_pct=6.0)
    assert result["breakdown"]["fund_flow"] == 8  # positive but rank > 500
    assert result["breakdown"]["lhb"] == 5  # not on LHB → neutral
    assert result["breakdown"]["turnover"] == 5


def test_akshare_api_error():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.side_effect = Exception("API error")
        mock_ak.stock_lhb_detail_daily_sina.side_effect = Exception("API error")
        mock_ak.stock_cyq_em.side_effect = Exception("API error")
        result = score_fund_chip("000001", "2026-07-10", turnover_pct=10.0)
    assert result["breakdown"]["fund_flow"] == 0
    assert result["breakdown"]["lhb"] == 5  # neutral fallback
    assert result["breakdown"]["chip"] == 0
    assert result["breakdown"]["turnover"] == 5
    assert result["total"] == 10


def test_penalty_continuous_outflow():
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", net_amount=-200_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001", net_buy=10_000_000)
        mock_ak.stock_cyq_em.return_value = _mock_cyq_df(concentration=10.0)
        result = score_fund_chip("000001", "2026-07-10", turnover_pct=8.0)
    # negative fund flow with cumulative > 1亿 → penalty triggers → total = 0
    assert result["total"] == 0


def test_cache_hit():
    clear_cache()
    with patch("services.scorer.fund_chip.akshare") as mock_ak:
        mock_ak.stock_fund_flow_individual.return_value = _mock_fund_flow_df("000001", net_amount=100_000_000)
        mock_ak.stock_lhb_detail_daily_sina.return_value = _mock_lhb_df("000001")
        mock_ak.stock_cyq_em.return_value = _mock_cyq_df(concentration=5.0)
        _ = score_fund_chip("000001", "2026-07-10", turnover_pct=8.0)
        call_count = mock_ak.stock_fund_flow_individual.call_count
        _ = score_fund_chip("000001", "2026-07-10", turnover_pct=8.0)
        assert mock_ak.stock_fund_flow_individual.call_count == call_count  # no new call


def test_score_fund_chip_empty_stock():
    result = score_fund_chip("000001", "2026-07-10", turnover_pct=None)
    assert result["total"] >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/api/tests/scorer/test_fund_chip.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

```python
# apps/api/services/scorer/fund_chip.py
"""资金筹码评分 (35分)"""
import logging
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

_cache: Dict[str, Any] = {}


def clear_cache():
    _cache.clear()


def _get_akshare():
    import akshare as ak
    return ak


def _batch_fund_flow(date_str: str, period: str = "3日排行") -> Optional[pd.DataFrame]:
    key = f"fund_flow_rank:{period}"
    if key in _cache:
        return _cache[key]
    try:
        ak = _get_akshare()
        df = ak.stock_fund_flow_individual(period)
        _cache[key] = df
        return df
    except Exception as e:
        logger.warning(f"akshare fund_flow_individual failed: {e}")
        return None


def _batch_lhb(date_str: str) -> Optional[pd.DataFrame]:
    key = f"lhb:{date_str}"
    if key in _cache:
        return _cache[key]
    try:
        ak = _get_akshare()
        # stock_lhb_detail_daily_sina uses format YYYYMMDD
        date_norm = date_str.replace("-", "")
        df = ak.stock_lhb_detail_daily_sina(date_norm)
        _cache[key] = df
        return df
    except Exception as e:
        logger.warning(f"akshare lhb failed: {e}")
        return None


def _fetch_cyq(code: str) -> Optional[pd.DataFrame]:
    key = f"cyq:{code}"
    if key in _cache:
        return _cache[key]
    try:
        ak = _get_akshare()
        df = ak.stock_cyq_em(code, adjust="qfq")
        _cache[key] = df
        return df
    except Exception as e:
        logger.warning(f"akshare cyq failed for {code}: {e}")
        return None


def score_fund_chip(code: str, date_str: str, turnover_pct: Optional[float] = None) -> Dict[str, Any]:
    fund_flow_score = 0
    lhb_score = 5   # default neutral
    chip_score = 0
    turnover_score = 0
    penalty = False

    # 2.1 主力资金净流入 (12pts)
    df = _batch_fund_flow(date_str)
    if df is not None and not df.empty and code in df["股票代码"].values:
        row = df[df["股票代码"] == code].iloc[0]
        net = float(row.get("净额", 0))
        rank = row.name + 1 if "股票代码" in df.columns else None  # row index + 1 as rank
        # Use the index to determine rank — stock_fund_flow_individual returns ranked by fund flow
        if net > 0:
            fund_flow_score = 12 if (rank is not None and rank <= 500) else 8
    # else: 0

    # 2.2 龙虎榜机构买入 (10pts)
    lhb_df = _batch_lhb(date_str)
    if lhb_df is not None and not lhb_df.empty:
        # Check if code is on the list
        code_suffix = code[-6:]  # handle codes with/without prefix
        in_lhb = lhb_df[lhb_df["股票代码"].astype(str).str.contains(code_suffix)]
        if not in_lhb.empty:
            net_buy = float(in_lhb.iloc[0].get("成交额(万元)", 0))
            if net_buy > 0:
                lhb_score = 10
            else:
                lhb_score = 0

    # 2.3 筹码集中度 (8pts)
    cyq_df = _fetch_cyq(code)
    if cyq_df is not None and not cyq_df.empty:
        latest = cyq_df.iloc[0]
        concentration = float(latest.get("90集中度", 30))
        if concentration < 10:
            chip_score = 8
        elif concentration <= 20:
            chip_score = 5
        else:
            chip_score = 2

    # 2.4 换手率 (5pts)
    if turnover_pct is not None:
        if 5 <= turnover_pct <= 18:
            turnover_score = 5
        elif (3 <= turnover_pct < 5) or (18 < turnover_pct <= 25):
            turnover_score = 3
        # else: 0

    # Penalty: continuous large outflow
    if df is not None and not df.empty and code in df["股票代码"].values:
        row = df[df["股票代码"] == code].iloc[0]
        net = float(row.get("净额", 0))
        if net < -100_000_000:  # > 1亿流出
            penalty = True

    total = 0 if penalty else (fund_flow_score + lhb_score + chip_score + turnover_score)

    return {
        "total": total,
        "breakdown": {
            "fund_flow": fund_flow_score,
            "lhb": lhb_score,
            "chip": chip_score,
            "turnover": turnover_score,
        },
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest apps/api/tests/scorer/test_fund_chip.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/services/scorer/fund_chip.py apps/api/tests/scorer/test_fund_chip.py
git commit -m "feat: add fund_chip scoring module"
```

---

### Task 4: `sector_theme.py` — 题材板块评分 (20分)

**Files:**
- Create: `apps/api/services/scorer/sector_theme.py`
- Create: `apps/api/tests/scorer/test_sector_theme.py`

Data source: akshare `stock_fund_flow_industry("3日排行")` + `stock_fund_flow_concept("3日排行")`.

Industry mapping: load `stock_industry.csv` at module init → `{pure_code: industry_name}` dict. Match industry names from akshare output by checking if the Shenwan industry name (e.g., "J66货币金融服务") contains a keyword that matches akshare industry name (e.g., "金融" or "货币金融").

For simplicity, build a small keyword-to-industry-name lookup:

```python
INDUSTRY_KEYWORDS = [
    ("银行", ["银行", "货币金融", "资本市场"]),
    ("证券", ["证券", "资本市场"]),
    ("保险", ["保险"]),
    ("房地产", ["房地产"]),
    ("医药生物", ["医药", "卫生"]),
    ("汽车", ["汽车"]),
    ("电子", ["电子"]),
    ("计算机", ["计算机", "软件", "互联网"]),
    ("通信", ["通信", "电信"]),
    ("食品饮料", ["食品", "饮料", "酒"]),
    ("化工", ["化工", "化学", "橡胶", "塑料"]),
    ("机械设备", ["设备", "机械", "仪器仪表"]),
    ("电力设备", ["电力", "电气"]),
    ("国防军工", ["国防", "军工", "船舶", "航空航天"]),
    ("有色金属", ["有色金属", "金属"]),
    ("煤炭", ["煤炭"]),
    ("建筑", ["建筑", "建材"]),
    ("交通运输", ["运输", "邮政", "仓储"]),
    ("商贸零售", ["批发", "零售", "贸易"]),
    ("传媒", ["传媒", "新闻", "出版", "广播", "电视", "电影"]),
    ("公用事业", ["电力、热力", "燃气", "水"]),
]
```

For each stock, find the keyword that matches its Shenwan industry name, and look up that keyword in the akshare industry ranking.

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/scorer/test_sector_theme.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch
import pandas as pd

from services.scorer.sector_theme import score_sector_theme, clear_cache, _industry_map


def setup_function():
    clear_cache()


def _mock_industry_df(keywords_top):
    """Mock stock_fund_flow_industry return. keywords_top = [(行业名称, 涨幅, 净额), ...]"""
    data = {
        "行业": [kw[0] for kw in keywords_top],
        "行业指数": [10.0] * len(keywords_top),
        "行业-涨跌幅": [kw[1] for kw in keywords_top],
        "净额": [kw[2] for kw in keywords_top],
    }
    return pd.DataFrame(data)


def _mock_concept_df(keywords_top):
    data = {
        "概念": [kw[0] for kw in keywords_top],
        "概念指数": [10.0] * len(keywords_top),
        "概念-涨跌幅": [kw[1] for kw in keywords_top],
        "净额": [kw[2] for kw in keywords_top],
    }
    return pd.DataFrame(data)


def test_sector_high_score():
    # J66货币金融服务 → matches "银行" via "货币金融" keyword → "银行" in akshare...
    # Actually let's just mock the industry map to return a known keyword
    with patch("services.scorer.sector_theme._batch_industry") as mock_ind:
        mock_ind.return_value = _mock_industry_df([
            ("银行", 3.5, 5_000_000_000),
            ("医药生物", 2.0, 2_000_000_000),
        ])
        with patch("services.scorer.sector_theme._batch_concept") as mock_conc:
            mock_conc.return_value = _mock_concept_df([
                ("国企改革", 4.0, 3_000_000_000),
            ])
            with patch("services.scorer.sector_theme.INDUSTRY_MAP", {"J66": "银行"}):
                result = score_sector_theme("000001", "2026-07-10", industry_code="J66")
    # Industry "银行" is rank 1 (top 5) → 12pts
    # Industry return > 3% → 5pts
    # Concept not matched (国企改革 doesn't match stock) → 0pts
    assert result["breakdown"]["industry_rank"] == 12
    assert result["breakdown"]["industry_return"] == 5
    assert result["total"] == 17


def test_sector_low_score():
    with patch("services.scorer.sector_theme._batch_industry") as mock_ind:
        mock_ind.return_value = _mock_industry_df([
            ("银行", -4.0, -1_000_000_000),
        ])
        with patch("services.scorer.sector_theme._batch_concept") as mock_conc:
            mock_conc.return_value = _mock_concept_df([])
            with patch("services.scorer.sector_theme.INDUSTRY_MAP", {"J66": "银行"}):
                result = score_sector_theme("000001", "2026-07-10", industry_code="J66")
    # Industry return < -3% → penalty → total = 0
    assert result["total"] == 0
    assert result["breakdown"]["industry_rank"] == 0


def test_sector_api_error():
    with patch("services.scorer.sector_theme._batch_industry") as mock_ind:
        mock_ind.return_value = None
        with patch("services.scorer.sector_theme._batch_concept") as mock_conc:
            mock_conc.return_value = None
            result = score_sector_theme("000001", "2026-07-10", industry_code="J66")
    assert result["total"] == 0


def test_sector_no_industry_code():
    result = score_sector_theme("000001", "2026-07-10", industry_code=None)
    assert result["total"] == 0


def test_industry_return_bonus():
    with patch("services.scorer.sector_theme._batch_industry") as mock_ind:
        mock_ind.return_value = _mock_industry_df([
            ("银行", 2.0, 5_000_000_000),
        ])
        with patch("services.scorer.sector_theme._batch_concept") as mock_conc:
            mock_conc.return_value = _mock_concept_df([])
            with patch("services.scorer.sector_theme.INDUSTRY_MAP", {"J66": "银行"}):
                result = score_sector_theme("000001", "2026-07-10", industry_code="J66")
    assert result["breakdown"]["industry_return"] == 3  # >1% but <3%


def test_concept_hot_match():
    with patch("services.scorer.sector_theme._batch_industry") as mock_ind:
        mock_ind.return_value = _mock_industry_df([])
        with patch("services.scorer.sector_theme._batch_concept") as mock_conc:
            mock_conc.return_value = _mock_concept_df([
               ("国企改革", 3.0, 2_000_000_000),
            ])
            with patch("services.scorer.sector_theme.CONCEPT_MAP", {"000001": "国企改革"}):
                result = score_sector_theme("000001", "2026-07-10", industry_code=None)
    assert result["breakdown"]["concept"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/api/tests/scorer/test_sector_theme.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# apps/api/services/scorer/sector_theme.py
"""题材板块评分 (20分)"""
import logging
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

_cache: Dict[str, Any] = {}

# Shenwan industry prefix → simplified industry keyword mapping
INDUSTRY_MAP = {
    "A01": "农业", "A02": "林业", "A03": "畜牧业", "A04": "渔业", "A05": "农业",
    "B06": "煤炭", "B07": "石油石化", "B08": "钢铁", "B09": "有色金属", "B10": "采掘",
    "C13": "食品饮料", "C14": "食品饮料", "C15": "食品饮料",
    "C17": "纺织服装", "C18": "纺织服装", "C19": "纺织服装",
    "C20": "轻工制造", "C21": "轻工制造", "C22": "轻工制造",
    "C23": "轻工制造", "C24": "轻工制造",
    "C25": "石油石化", "C26": "化工", "C27": "医药生物", "C28": "化工",
    "C29": "化工", "C30": "建筑材料", "C31": "钢铁", "C32": "有色金属",
    "C33": "机械设备", "C34": "机械设备", "C35": "机械设备",
    "C36": "汽车", "C37": "国防军工", "C38": "电力设备", "C39": "电子",
    "C40": "机械设备", "C41": "综合", "C42": "综合",
    "D44": "公用事业", "D45": "公用事业", "D46": "公用事业",
    "E47": "建筑装饰", "E48": "建筑装饰", "E49": "建筑装饰", "E50": "建筑装饰",
    "F51": "商贸零售", "F52": "商贸零售",
    "G53": "交通运输", "G54": "交通运输", "G55": "交通运输", "G56": "交通运输",
    "G58": "交通运输", "G59": "交通运输", "G60": "交通运输",
    "H61": "社会服务", "H62": "社会服务",
    "I63": "通信", "I64": "传媒", "I65": "计算机",
    "J66": "银行", "J67": "非银金融", "J68": "非银金融", "J69": "非银金融",
    "K70": "房地产",
    "L71": "社会服务", "L72": "社会服务",
    "M73": "社会服务", "M74": "社会服务", "M75": "综合",
    "N76": "公用事业", "N77": "公用事业", "N78": "综合",
    "P83": "社会服务",
    "Q84": "医药生物",
    "R86": "传媒", "R87": "传媒", "R88": "传媒", "R89": "社会服务",
    "S91": "综合",
}

CONCEPT_MAP: Dict[str, str] = {}  # filled at runtime from CSV


def clear_cache():
    _cache.clear()


def _batch_industry(date_str: str, period: str = "3日排行") -> Optional[pd.DataFrame]:
    key = f"industry_flow:{period}"
    if key in _cache:
        return _cache[key]
    try:
        import akshare as ak
        df = ak.stock_fund_flow_industry(period)
        _cache[key] = df
        return df
    except Exception as e:
        logger.warning(f"akshare industry flow failed: {e}")
        return None


def _batch_concept(date_str: str, period: str = "3日排行") -> Optional[pd.DataFrame]:
    key = f"concept_flow:{period}"
    if key in _cache:
        return _cache[key]
    try:
        import akshare as ak
        df = ak.stock_fund_flow_concept(period)
        _cache[key] = df
        return df
    except Exception as e:
        logger.warning(f"akshare concept flow failed: {e}")
        return None


def score_sector_theme(code: str, date_str: str,
                       industry_code: Optional[str] = None) -> Dict[str, Any]:
    industry_rank_score = 0
    industry_return_score = 0
    concept_score = 0

    if not industry_code:
        return {"total": 0, "breakdown": {"industry_rank": 0, "industry_return": 0, "concept": 0}}

    # Map stock industry code to simplified keyword
    # industry_code looks like "J66" or "J66货币金融服务"
    prefix = "".join(c for c in industry_code if c.isalpha()).upper()
    industry_keyword = INDUSTRY_MAP.get(prefix)

    # Get industry fund flow ranking
    df = _batch_industry(date_str)
    if df is not None and not df.empty and industry_keyword:
        industry_names = df["行业"].tolist()
        # Find position of the stock's industry in the ranking
        for idx, name in enumerate(industry_names):
            if industry_keyword in name:
                rank = idx + 1
                if rank <= 5:
                    industry_rank_score = 12
                elif rank <= 10:
                    industry_rank_score = 8
                elif rank <= 20:
                    industry_rank_score = 4

                # 3.2 Industry index return
                ret = float(df.iloc[idx].get("行业-涨跌幅", 0))
                if ret > 3:
                    industry_return_score = 5
                elif ret > 1:
                    industry_return_score = 3

                # Penalty: industry return < -3%
                if ret < -3:
                    return {"total": 0, "breakdown": {"industry_rank": 0, "industry_return": 0, "concept": 0}}
                break

    # 3.3 Concept热点
    conc_df = _batch_concept(date_str)
    if conc_df is not None and not conc_df.empty:
        concept_names = conc_df["概念"].tolist()
        # Check if any hot concept matches the stock's known concepts
        stock_concepts = CONCEPT_MAP.get(code, [])
        if isinstance(stock_concepts, str):
            stock_concepts = [stock_concepts]
        for hot_conc in concept_names[:5]:
            for sc in stock_concepts:
                if isinstance(sc, str) and hot_conc in sc:
                    concept_score = 3
                    break
            if concept_score > 0:
                break

    total = industry_rank_score + industry_return_score + concept_score

    return {
        "total": total,
        "breakdown": {
            "industry_rank": industry_rank_score,
            "industry_return": industry_return_score,
            "concept": concept_score,
        },
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest apps/api/tests/scorer/test_sector_theme.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/services/scorer/sector_theme.py apps/api/tests/scorer/test_sector_theme.py
git commit -m "feat: add sector_theme scoring module"
```

---

### Task 5: `risk_check.py` — 极简风控 (5分)

**Files:**
- Create: `apps/api/services/scorer/risk_check.py`
- Create: `apps/api/tests/scorer/test_risk_check.py`

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/scorer/test_risk_check.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch, MagicMock
import pandas as pd

from services.scorer.risk_check import score_risk, clear_cache


def setup_function():
    clear_cache()


def test_clean_stock():
    """No ST, no delisting, no restricted release → 5pts"""
    with patch("services.scorer.risk_check._fetch_restricted_release") as mock_rr:
        mock_rr.return_value = None  # no restricted release
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 5


def test_st_stock():
    """ST stock → total = 0 (veto)"""
    with patch("services.scorer.risk_check._fetch_restricted_release") as mock_rr:
        mock_rr.return_value = None
        result = score_risk("600001", "ST华业", "2026-07-10")
    assert result["total"] == 0
    assert result["veto"] is True


def test_delisting_risk():
    """退市预警 → veto"""
    with patch("services.scorer.risk_check._fetch_restricted_release") as mock_rr:
        mock_rr.return_value = None
        result = score_risk("000001", "TestCorp", "2026-07-10", delisting_risk=True)
    assert result["total"] == 0
    assert result["veto"] is True


def test_restricted_release_today():
    with patch("services.scorer.risk_check._fetch_restricted_release") as mock_rr:
        mock_rr.return_value = [
            {"date": "2026-07-10", "code": "000001"},
        ]
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 4  # ST(2) + delisting(2) but no bad_news(1)


def test_name_contains_ST():
    """Stock name contains ST at any position"""
    for name in ["ST华业", "*ST信威", "退市金钰"]:
        result = score_risk("000001", name, "2026-07-10")
        assert result["total"] == 0, f"Failed for name: {name}"


def test_code_300_veto():
    """创业板的 300 代码 → 风控仍需通过 (风控不决定创业板排除，入口层决定)"""
    # 300 stocks are excluded before scoring, so this test is about non-ST 300 stocks
    with patch("services.scorer.risk_check._fetch_restricted_release") as mock_rr:
        mock_rr.return_value = None
        result = score_risk("300750", "宁德时代", "2026-07-10")
    assert result["total"] == 5  # 300 stocks are NOT ST, should pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/api/tests/scorer/test_risk_check.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# apps/api/services/scorer/risk_check.py
"""极简风控 (5分, 硬否决)"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

_cache: Dict[str, Any] = {}

DELISTING_CODES = set()  # to be populated from external source


def clear_cache():
    _cache.clear()


def is_st(name: str) -> bool:
    if not name:
        return False
    # Check for ST / *ST / 退 / 退市 markers
    name_upper = name.upper().replace("*", "")
    return "ST" in name_upper or "退" in name or "退市" in name


def _fetch_restricted_release(date_str: str) -> Optional[List[dict]]:
    key = f"restricted_release:{date_str}"
    if key in _cache:
        return _cache[key]
    try:
        import akshare as ak
        date_norm = date_str.replace("-", "")
        df = ak.stock_restricted_release_detail_em(date=date_norm)
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row.get("解禁日期", "")),
                    "code": str(row.get("股票代码", "")),
                })
            _cache[key] = records
            return records
        _cache[key] = []
        return []
    except Exception as e:
        logger.warning(f"Failed to fetch restricted release data: {e}")
        _cache[key] = []  # don't retry this date
        return []


def score_risk(code: str, name: str, date_str: str,
               delisting_risk: bool = False) -> Dict[str, Any]:
    st_score = 0
    delist_score = 0
    news_score = 0

    # ST check (veto)
    if is_st(name):
        return {"total": 0, "veto": True, "breakdown": {"st": 0, "delist": 0, "bad_news": 0}}

    st_score = 2

    # Delisting risk (veto)
    if delisting_risk or code in DELISTING_CODES:
        return {"total": 0, "veto": True, "breakdown": {"st": 2, "delist": 0, "bad_news": 0}}

    delist_score = 2

    # Restricted release / bad news check
    records = _fetch_restricted_release(date_str)
    has_release = False
    if records:
        for rec in records:
            if rec["date"] == date_str and code in rec["code"]:
                has_release = True
                break

    if not has_release:
        news_score = 1

    total = st_score + delist_score + news_score

    return {
        "total": total,
        "veto": total < 4,  # veto means total = 0 already → this is just metadata
        "breakdown": {"st": st_score, "delist": delist_score, "bad_news": news_score},
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest apps/api/tests/scorer/test_risk_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/services/scorer/risk_check.py apps/api/tests/scorer/test_risk_check.py
git commit -m "feat: add risk_check scoring module"
```

---

### Task 6: `stock_scorer.py` — 统一评分入口

**Files:**
- Create: `apps/api/services/stock_scorer.py`
- Create: `apps/api/tests/test_stock_scorer.py`

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/test_stock_scorer.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from services.stock_scorer import StockScorer


def test_score_basic():
    """Full score() returns expected structure"""
    with patch("services.stock_scorer.get_db") as mock_db:
        mock_db.return_value.stock_kline.find.return_value.sort.return_value.limit.return_value = []
        scorer = StockScorer()
        result = scorer.score("000001", "Test", "2026-07-10")
    assert "code" in result
    assert "total" in result
    assert "level" in result
    assert "breakdown" in result
    assert result["code"] == "000001"
    assert isinstance(result["total"], (int, float))


def test_score_levels():
    """Level classification: S >= 80, A >= 60, B >= 40, C < 40"""
    with patch("services.stock_scorer.get_db") as mock_db, \
         patch("services.stock_scorer.score_price_volume") as mock_pv, \
         patch("services.stock_scorer.score_fund_chip") as mock_fc, \
         patch("services.stock_scorer.score_sector_theme") as mock_st, \
         patch("services.stock_scorer.score_risk") as mock_rc:

        mock_db.return_value.stock_kline.find.return_value.sort.return_value.limit.return_value = []
        mock_pv.return_value = {"total": 35, "breakdown": {}}
        mock_fc.return_value = {"total": 30, "breakdown": {}}
        mock_st.return_value = {"total": 15, "breakdown": {}}
        mock_rc.return_value = {"total": 5, "veto": False, "breakdown": {}}
        scorer = StockScorer()
        result = scorer.score("000001", "Test", "2026-07-10")
        assert result["total"] == 85
        assert result["level"] == "S"


def test_veto_zeroes_total():
    """Risk veto sets total to 0"""
    with patch("services.stock_scorer.get_db") as mock_db, \
         patch("services.stock_scorer.score_price_volume") as mock_pv, \
         patch("services.stock_scorer.score_fund_chip") as mock_fc, \
         patch("services.stock_scorer.score_sector_theme") as mock_st, \
         patch("services.stock_scorer.score_risk") as mock_rc:

        mock_db.return_value.stock_kline.find.return_value.sort.return_value.limit.return_value = []
        mock_pv.return_value = {"total": 40, "breakdown": {}}
        mock_fc.return_value = {"total": 35, "breakdown": {}}
        mock_st.return_value = {"total": 20, "breakdown": {}}
        mock_rc.return_value = {"total": 0, "veto": True, "breakdown": {}}
        scorer = StockScorer()
        result = scorer.score("000001", "Test", "2026-07-10")
        assert result["total"] == 0


def test_stock_code_filter():
    """入口层过滤: 300/688/index/ST 直接返回 total=0"""
    for code in ["300750", "688001", "000001"]:
        with patch("services.stock_scorer.get_db") as mock_db:
            if code == "000001":
                mock_db.return_value.stock_kline.find.return_value.sort.return_value.limit.return_value = []
                scorer = StockScorer()
                result = scorer.score(code, "Test", "2026-07-10")
                assert result["total"] >= 0  # should go through normal scoring
            else:
                scorer = StockScorer()
                result = scorer.score(code, "Test", "2026-07-10")
                assert result["total"] == 0  # filtered out


def test_date_default():
    """Default date is today"""
    with patch("services.stock_scorer.get_db") as mock_db:
        mock_db.return_value.stock_kline.find.return_value.sort.return_value.limit.return_value = []
        scorer = StockScorer()
        result = scorer.score("000001", "Test")
    assert "date" in result
    assert result["date"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/api/tests/test_stock_scorer.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# apps/api/services/stock_scorer.py
"""统一评分入口"""
import logging
from datetime import date, datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class StockScorer:
    MODE_SHORT = "short"

    def __init__(self, db=None):
        self._db = db

    def _get_db(self):
        if self._db is None:
            from database import get_db
            self._db = get_db()
        return self._db

    def _is_filtered(self, code: str, name: str) -> bool:
        pure = code.split(".")[-1] if "." in code else code
        if not (pure.isdigit() and len(pure) == 6):
            return True
        if pure.startswith(("300", "688")):
            return True
        if name:
            name_upper = name.upper().replace("*", "")
            if "ST" in name_upper or "退" in name:
                return True
        return False

    def _load_industry_code(self, code: str) -> Optional[str]:
        try:
            db = self._get_db()
            from systems.sys import home
            import os
            path = os.path.join(home(), "apps", "api", "data", "stock_industry.csv")
            if os.path.exists(path):
                import pandas as pd
                df = pd.read_csv(path)
                # code in CSV has "sh." or "sz." prefix
                for _, row in df.iterrows():
                    csv_code = str(row.get("code", "")).strip()
                    if code in csv_code:
                        raw = str(row.get("industry", "")).strip()
                        if raw and raw != "证监会行业分类":
                            return raw
            # Fallback: code_to_industry.csv
            path2 = os.path.join(home(), "apps", "api", "data", "code_to_industry.csv")
            if os.path.exists(path2):
                df2 = pd.read_csv(path2)
                for _, row in df2.iterrows():
                    if str(row.get("code", "")).strip() == code or str(row.get("code", "")).strip() == pure:
                        return str(row.get("industry", "")).strip()
        except Exception as e:
            logger.warning(f"Failed to load industry for {code}: {e}")
        return None

    def _load_turnover(self, code: str, date_str: str) -> Optional[float]:
        try:
            db = self._get_db()
            from database import get_db as _get_db
            db = self._get_db()
            # Try to get today's 5m klines to estimate turnover from volume
            bars = list(db.stock_kline_5m.find(
                {"code": code, "date": {"$regex": f"^{date_str}"}}
            ).limit(5))
            if bars:
                total_vol = sum(b.get("volume", 0) for b in bars)
                if total_vol > 0:
                    return min(total_vol / 1_0000, 30)  # rough estimate, cap at 30%
            # Also check daily kline turnover if available
            daily = db.stock_kline.find_one({"code": code, "date": date_str})
            if daily and daily.get("turnover"):
                return float(daily["turnover"])
        except Exception:
            pass
        return None

    def score(self, code: str, name: str = "",
              date_str: Optional[str] = None) -> Dict[str, Any]:
        if date_str is None:
            date_str = date.today().strftime("%Y-%m-%d")

        # Filter layer
        if self._is_filtered(code, name):
            return {"code": code, "name": name, "date": date_str,
                    "total": 0, "level": "C",
                    "breakdown": {"price_volume": {}, "fund_chip": {},
                                  "sector_theme": {}, "risk": {}}}

        # Load K-lines
        db = self._get_db()
        klines = list(db.stock_kline.find(
            {"code": code, "date": {"$lte": date_str}}
        ).sort("date", -1).limit(60))

        industry_code = self._load_industry_code(code)
        turnover_pct = self._load_turnover(code, date_str)

        # 4 sub-modules
        from services.scorer.price_volume import score_price_volume
        from services.scorer.fund_chip import score_fund_chip
        from services.scorer.sector_theme import score_sector_theme
        from services.scorer.risk_check import score_risk

        pv = score_price_volume(klines, date_str)
        fc = score_fund_chip(code, date_str, turnover_pct=turnover_pct)
        st = score_sector_theme(code, date_str, industry_code=industry_code)
        rc = score_risk(code, name, date_str)

        total = pv["total"] + fc["total"] + st["total"] + rc["total"]

        # Risk veto overrides everything
        if rc.get("veto") or total == 0:
            total = 0

        if total >= 80:
            level = "S"
        elif total >= 60:
            level = "A"
        elif total >= 40:
            level = "B"
        else:
            level = "C"

        return {
            "code": code, "name": name, "date": date_str,
            "total": total, "level": level,
            "breakdown": {
                "price_volume": pv,
                "fund_chip": fc,
                "sector_theme": st,
                "risk": rc,
            },
        }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest apps/api/tests/test_stock_scorer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/services/stock_scorer.py apps/api/tests/test_stock_scorer.py
git commit -m "feat: add StockScorer unified entry point"
```

---

### Task 7: Modify `review_picker.py` — 集成 StockScorer

**Files:**
- Modify: `apps/api/bin/review_picker.py`

Replace `calc_score()` function and scoring logic with `StockScorer.score()`.

New flow:
1. `load_stocks()` unchanged (still filters 300/688/ST/indexes)
2. After `ReviewService.analyze()` returns, call `StockScorer.score()` with the code + name
3. Use `StockScorer`'s total for ranking (keep the "只取持有结论" filter)
4. Replace `build_message()` to use StockScorer output format

- [ ] **Step 1: Read `review_picker.py` to understand current flow**

- [ ] **Step 2: Apply changes**

Edit `apps/api/bin/review_picker.py`:

In `calc_score()`: Keep the "only 持有 passes" gate but replace score computation with StockScorer:
```python
def calc_score(r: Dict[str, Any]) -> float:
    if r["conclusion"] != "持有":
        return -1
    scorer = StockScorer()
    result = scorer.score(r["code"], r["name"], r.get("date", date.today().strftime("%Y-%m-%d")))
    return result["total"]
```

Also update `build_message()` to use `level` from the worst stock in the message:
```python
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

    lines = [
        "━" * 20,
        f"🔍 **{top_r['code']} {top_r['name']}**",
        f"📈 评分：**{top_s:.0f}分**",
        f"📌 日线定位：{top_r['position']}",
        f"📊 均价分析：{top_r['vwap_status']}",
        f"📋 量能分析：{top_r['volume_signal']}",
        f"🔎 分时形态：{top_r['pattern']}",
        f"🌙 尾盘信号：{top_r['tail_signal']}",
        f"⏱ 策略：{top_r['strategy']}",
        "---",
        f"共评分 {len(scored)} 只股票，当前第一",
    ]
    title = f"明日关注 ({top_r['code']})"
    return title, "\n".join(lines)
```

Add import:
```python
from services.stock_scorer import StockScorer
```

- [ ] **Step 3: Run quick smoke test**

Run: `python -c "from services.stock_scorer import StockScorer; s=StockScorer(); r=s.score('600519','贵州茅台','2026-07-10'); print(r['total'], r['level'])"`
Expected: Runs without error

- [ ] **Step 4: Commit**

```bash
git add apps/api/bin/review_picker.py
git commit -m "feat: integrate StockScorer into review_picker"
```

---

### Task 8: Modify `rule_engine.py` — 集成 StockScorer

**Files:**
- Modify: `apps/api/bin/rule_engine.py`

Change the buy signal logic: after collecting candidates, sort by StockScorer score and only push if >= 60.

- [ ] **Step 1: Read the integration point in `rule_engine.py` (around line 485-520)**

- [ ] **Step 2: Apply changes**

Add import:
```python
from services.stock_scorer import StockScorer
```

In the buy signal section (after collecting candidates in the `buy_candidates` list):
```python
# Old:
if buy_candidates:
    buy_candidates.sort(key=lambda x: x["buy_score"], reverse=True)
    best = buy_candidates[0]

# New:
if buy_candidates:
    scorer = StockScorer()
    for c in buy_candidates:
        result = scorer.score(c["code"], c["name"])
        c["scorer_score"] = result["total"]
        c["scorer_level"] = result["level"]

    buy_candidates.sort(key=lambda x: x["scorer_score"], reverse=True)
    best = buy_candidates[0]

    if best["scorer_score"] < 60:
        logging.info(f"Best candidate {best['code']} {best['name']} score={best['scorer_score']} < 60, skipping")
        buy_candidates = []
        best = None

if best:
    msg = (
        f"📈 **买入信号** {best['code']} {best['name']}\n"
        f"**短线评分**: {best['scorer_score']:.0f}分（等级{best['scorer_level']}）\n"
        f"**触发规则**: {best['rule_names']}\n"
        f"**当前价**: {best['price']:.2f}\n"
        ...
    )
```

- [ ] **Step 3: Run quick smoke test**

Run: `python -c "from services.stock_scorer import StockScorer; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add apps/api/bin/rule_engine.py
git commit -m "feat: integrate StockScorer into rule_engine"
```

---

### Task 9: Modify `backtest_engine.py` — 集成 StockScorer

**Files:**
- Modify: `apps/api/services/backtest_engine.py`

Add StockScorer filtering to the buy logic.

- [ ] **Step 1: Read the integration point (around line 296-306)**

- [ ] **Step 2: Apply changes**

Add import at top:
```python
from services.stock_scorer import StockScorer
```

Change:
```python
# Old:
_, _, buy_score, _ = engine.run(ctx)
if buy_score > 0:
    buy_candidates.append((buy_score, code))

# New:
_, _, buy_score, _ = engine.run(ctx)
if buy_score > 0:
    scorer_result = StockScorer().score(code, name_map.get(code, ""), date_str)
    if scorer_result["total"] >= 60:
        buy_candidates.append((scorer_result["total"], code))
```

- [ ] **Step 3: Run quick smoke test**

Run: `python -c "from services.backtest_engine import _build_ctx; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add apps/api/services/backtest_engine.py
git commit -m "feat: integrate StockScorer into backtest_engine"
```

---

### Task 10: Full integration test

Run all scorer tests together:

```bash
python -m pytest apps/api/tests/scorer/ -v
python -m pytest apps/api/tests/test_stock_scorer.py -v
```

Verify lint:
```bash
python -m flake8 apps/api/services/scorer/ apps/api/services/stock_scorer.py
```

If any test fails, fix the implementation. If lint issues found, fix style.
