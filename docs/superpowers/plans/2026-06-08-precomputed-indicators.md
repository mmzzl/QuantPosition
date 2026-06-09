# Pre-computed Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pre-compute all stock technical indicators into MongoDB daily so backtests read pre-computed values instead of re-calculating in backtrader, eliminating indicator computation overhead for ~125k bar evaluations.

**Architecture:** Three-tier: (1) core computation functions with Wilder formulas in `indicator_calculator.py`, (2) daily Celery task + scheduler script to compute indicators for stocks with new klines, (3) backtest engine loads pre-computed values and skips all backtrader indicator lines. One-time backfill covers all historical data.

**Tech Stack:** Python 3.12, MongoDB (pymongo), Celery, backtrader

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `apps/api/bin/rule_engine.py` | Modify | Replace `calc_rsi` and `calc_atr` with Wilder equivalents; update `build_stock_indicators` to call them |
| `apps/api/bin/indicator_calculator.py` | Create | Core computation logic + `__main__` for daily scheduler update + backfill |
| `apps/api/tasks/indicator_tasks.py` | Create | Celery tasks `tasks.indicators.update` and `tasks.indicators.backfill` |
| `apps/api/tasks/__init__.py` | Modify | Import new task module |
| `apps/api/celery_config.py` | Modify | Register `"indicator_tasks"` in `_TASK_MODULES` |
| `apps/api/database.py` | Modify | Add `stock_indicators` index |
| `apps/api/services/backtest_engine.py` | Modify | Load pre-computed indicators; drop backtrader indicator creation; read pre-computed values in `_ctx()` |
| `apps/api/config/inputs.conf` | Modify | Add daily indicator update schedule |

---

## Task 1: Add Wilder RSI and Wilder ATR to rule_engine.py

**Files:**
- Modify: `apps/api/bin/rule_engine.py`

- [ ] **Step 1: Replace `calc_rsi` with Wilder RSI**

Old function at line 143:

```python
def calc_rsi(prices, period=14):
    """RSI 相对强弱指标"""
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
```

Replace with:

```python
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
```

- [ ] **Step 2: Replace `calc_atr` with Wilder ATR**

Old function at line 158:

```python
def calc_atr(highs, lows, closes, period=14):
    """ATR 真实波动幅度"""
    if len(closes) < period + 1:
        return (highs[-1] - lows[-1]) if (highs[-1] - lows[-1]) > 0 else 0
    trs = []
    for i in range(1, len(highs)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i-1]),
                 abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return sum(trs[-period:]) / period
```

Replace with:

```python
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
```

- [ ] **Step 3: Run a quick compilation check**

```bash
cd D:\home\apps\api
python -c "import py_compile; py_compile.compile('bin/rule_engine.py', doraise=True)"
```

Expected: no error.

- [ ] **Step 4: Commit**

```bash
cd D:\home
git add apps/api/bin/rule_engine.py
git commit -m "feat: calc_rsi/calc_atr 改为 Wilder 平滑公式，匹配 backtrader"
```

---

## Task 2: Create indicator_calculator.py (core logic + standalone script)

**Files:**
- Create: `apps/api/bin/indicator_calculator.py`

- [ ] **Step 1: Create the file with core pure functions + batch computation + `__main__`**

Write `apps/api/bin/indicator_calculator.py`:

```python
# -*- coding: utf-8 -*-
"""指标预计算：每天盘后计算全市场股票技术指标存入 stock_indicators 集合

支持两种运行模式：
  1. python bin/indicator_calculator.py        # 每日增量更新（只有今天有数据的股票）
  2. python bin/indicator_calculator.py backfill  # 一次性回填所有历史数据
"""
import sys
import os
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from bin.rule_engine import calc_sma, calc_rsi, calc_atr, calc_adx

logger = logging.getLogger(__name__)


def compute_stock_indicators(klines):
    """从 K 线列表计算所有技术指标

    Args:
        klines: list of dicts with keys [code, date, open, high, low, close, volume]
                sorted by date ASC. Must include at least 20 bars.

    Returns:
        (dict of {date_str: {ma5, ma10, ..., amplitude}}, or None if insufficient data)
    """
    if len(klines) < 20:
        logger.warning("compute_stock_indicators: 数据不足 %d 条", len(klines))
        return None

    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]

    results = {}
    for i in range(len(klines)):
        date_str = klines[i]["date"][:10]
        cur_close = closes[i]
        prev_close = closes[i - 1] if i >= 1 else cur_close
        open_val = klines[i].get("open", 0)

        window_closes = closes[:i + 1]
        window_volumes = volumes[:i + 1]
        window_highs = highs[:i + 1]
        window_lows = lows[:i + 1]

        high20 = max(window_highs[-20:]) if len(window_highs) >= 20 else window_highs[-1]
        low20 = min(window_lows[-20:]) if len(window_lows) >= 20 else window_lows[-1]
        amplitude = (highs[i] - lows[i]) / prev_close if prev_close > 0 else 0

        results[date_str] = {
            "close": cur_close,
            "volume": volumes[i],
            "ma5": calc_sma(window_closes, 5),
            "ma10": calc_sma(window_closes, 10),
            "ma20": calc_sma(window_closes, 20),
            "ma60": calc_sma(window_closes, 60),
            "ma5_vol": calc_sma(window_volumes, 5),
            "last_close": prev_close,
            "high20": high20,
            "low20": low20,
            "open": open_val,
            "rsi": calc_rsi(window_closes),
            "atr": calc_atr(window_highs, window_lows, window_closes),
            "adx": calc_adx(window_highs, window_lows, window_closes),
            "amplitude": amplitude,
        }

    return results


def get_codes_with_klines_today(db, today_str):
    """查询今天有 K 线数据的股票代码列表"""
    today_end = f"{today_str} 15:00"
    codes = db.stock_kline.distinct("code", {
        "frequency": 9,
        "date": today_end,
    })
    return codes


def update_stock_indicators(db, codes, warmup_days=60, backfill=False):
    """为指定股票更新区间内的指标（upsert 到 stock_indicators）

    Args:
        db: MongoDB 数据库对象
        codes: 股票代码列表
        warmup_days: 每日更新时加载的历史天数
        backfill: 是否回填所有历史

    Returns:
        (updated_count, error_count)
    """
    if backfill:
        start_str = "2000-01-01"
        end_str = datetime.now().strftime("%Y-%m-%d") + " 23:59"
    else:
        today = datetime.now()
        start_str = (today - timedelta(days=warmup_days)).strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d") + " 23:59"

    stock_klines = _batch_load_klines(db, codes, start_str, end_str)

    updated = 0
    errors = 0
    for code in codes:
        klines = stock_klines.get(code, [])
        if not klines:
            continue
        try:
            indicators = compute_stock_indicators(klines)
            if indicators is None:
                continue
            _upsert_indicators(db, code, indicators)
            updated += 1
        except Exception as e:
            logger.error("计算 %s 指标失败: %s", code, e)
            errors += 1

    return updated, errors


def backfill_all_indicators(db, chunk_size=200):
    """回填所有股票的所有历史指标"""
    all_codes = db.stock_kline.distinct("code", {"frequency": 9})
    logger.info("回填指标: 共 %d 只股票", len(all_codes))

    total_updated = 0
    total_errors = 0
    for i in range(0, len(all_codes), chunk_size):
        chunk = all_codes[i:i + chunk_size]
        updated, errors = update_stock_indicators(db, chunk, backfill=True)
        total_updated += updated
        total_errors += errors
        logger.info("回填进度: %d/%d (更新 %d, 错误 %d)",
                     min(i + chunk_size, len(all_codes)), len(all_codes),
                     total_updated, total_errors)

    logger.info("回填完成: 更新 %d 只, 错误 %d 只", total_updated, total_errors)
    return total_updated, total_errors


def _batch_load_klines(db, codes, start_str, end_str):
    """批量加载给定股票在时间范围内的 K 线"""
    raw = list(db.stock_kline.find(
        {"code": {"$in": codes}, "frequency": 9,
         "date": {"$gte": start_str, "$lte": end_str}},
        {"code": 1, "date": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ).sort("date", 1))

    result = {}
    for k in raw:
        result.setdefault(k["code"], []).append(k)
    return result


def _upsert_indicators(db, code, indicators):
    """批量 upsert 指标数据到 stock_indicators (使用 bulk_write 加速)"""
    from pymongo import UpdateOne
    requests = []
    now = datetime.now()
    for date_str, vals in indicators.items():
        doc = {"code": code, "date": date_str, **vals, "created_at": now}
        requests.append(UpdateOne(
            {"code": doc["code"], "date": doc["date"]},
            {"$set": doc},
            upsert=True,
        ))
    if requests:
        db.stock_indicators.bulk_write(requests, ordered=False)


def run_daily_update():
    """每日更新：为今天有 K 线的股票计算指标"""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    db = get_db()
    today_str = datetime.now().strftime("%Y-%m-%d")
    codes = get_codes_with_klines_today(db, today_str)
    logger.info("今日有 K 线的股票: %d 只", len(codes))
    if not codes:
        logger.info("今日无新 K 线数据，跳过")
        return
    updated, errors = update_stock_indicators(db, codes)
    logger.info("每日指标更新完成: 成功 %d 只, 失败 %d 只", updated, errors)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(message)s")
        db = get_db()
        backfill_all_indicators(db)
    else:
        run_daily_update()
```

- [ ] **Step 2: Verify compilation**

```bash
cd D:\home\apps\api
python -c "import py_compile; py_compile.compile('bin/indicator_calculator.py', doraise=True)"
```

Expected: no error.

- [ ] **Step 3: Commit**

```bash
cd D:\home
git add apps/api/bin/indicator_calculator.py
git commit -m "feat: 指标预计算核心逻辑 + 每日更新/回填脚本"
```

---

## Task 3: Create indicator_tasks.py + register in Celery

**Files:**
- Create: `apps/api/tasks/indicator_tasks.py`
- Modify: `apps/api/tasks/__init__.py`
- Modify: `apps/api/celery_config.py`

- [ ] **Step 1: Create `apps/api/tasks/indicator_tasks.py`**

```python
import logging
from celery_config import celery_app
from bin.indicator_calculator import run_daily_update, backfill_all_indicators
from database import get_db


@celery_app.task(bind=True, name="tasks.indicators.update")
def update_indicators(self):
    """Celery 任务：每日指标更新"""
    self.update_state(state='PROGRESS', meta={'status': '开始更新指标...'})
    run_daily_update()
    return {"status": "ok"}


@celery_app.task(bind=True, name="tasks.indicators.backfill")
def backfill_indicators(self):
    """Celery 任务：回填所有历史指标"""
    self.update_state(state='PROGRESS', meta={'status': '开始回填指标...'})
    db = get_db()
    updated, errors = backfill_all_indicators(db)
    return {"updated": updated, "errors": errors}
```

- [ ] **Step 2: Add import to `apps/api/tasks/__init__.py`**

Old content:
```python
from .selection_tasks import *
from .news_selection_tasks import *
from .kline_tasks import *
```

New content:
```python
from .selection_tasks import *
from .news_selection_tasks import *
from .kline_tasks import *
from .indicator_tasks import *
```

- [ ] **Step 3: Register module in `apps/api/celery_config.py`**

Old line 31-33:
```python
_TASK_MODULES = [
    "selection_tasks", "news_selection_tasks", "kline_tasks",
    "backtest_tasks", "rule_explore_tasks", "heatmap_selection_tasks",
]
```

New:
```python
_TASK_MODULES = [
    "selection_tasks", "news_selection_tasks", "kline_tasks",
    "backtest_tasks", "rule_explore_tasks", "heatmap_selection_tasks",
    "indicator_tasks",
]
```

- [ ] **Step 4: Verify compilation**

```bash
cd D:\home\apps\api
python -c "import py_compile; py_compile.compile('tasks/indicator_tasks.py', doraise=True); py_compile.compile('tasks/__init__.py', doraise=True); py_compile.compile('celery_config.py', doraise=True)"
```

Expected: no error.

- [ ] **Step 5: Commit**

```bash
cd D:\home
git add apps/api/tasks/indicator_tasks.py apps/api/tasks/__init__.py apps/api/celery_config.py
git commit -m "feat: Celery 任务 tasks.indicators.update + backfill"
```

---

## Task 4: Add stock_indicators index to database.py

**Files:**
- Modify: `apps/api/database.py`

- [ ] **Step 1: Add index creation in `_ensure_indexes`**

Before the function closing (before line 77 `def query_sort_end...`), add:

```python
    # Stock indicators collection indexes
    db.stock_indicators.create_index([("code", ASCENDING), ("date", DESCENDING)])
    db.stock_indicators.create_index([("date", DESCENDING)])
```

- [ ] **Step 2: Verify compilation**

```bash
cd D:\home\apps\api
python -c "import py_compile; py_compile.compile('database.py', doraise=True)"
```

Expected: no error.

- [ ] **Step 3: Commit**

```bash
cd D:\home
git add apps/api/database.py
git commit -m "feat: stock_indicators 集合索引"
```

---

## Task 5: Update backtest_engine.py to use pre-computed indicators

**Files:**
- Modify: `apps/api/services/backtest_engine.py`

This is the largest change. The key modifications:
1. Add `_load_aligned_indicators()` function to load pre-computed data from MongoDB
2. Update `run_backtest()` to call it and pass to strategy
3. Remove all backtrader indicator creation from `__init__`
4. Rewrite `_ctx()` to read from pre-computed dict

- [ ] **Step 1: Add `_load_aligned_indicators` function (after `_load_aligned_klines`)**

Add this after line 114 (end of `_load_aligned_klines`):

```python
def _load_aligned_indicators(codes, start, end):
    """从 stock_indicators 加载预计算指标

    Returns:
        {code: {date_str: {ma5, ma10, ..., adx, amplitude}}}
    """
    db = get_db()
    raw = list(db.stock_indicators.find(
        {"code": {"$in": codes}, "date": {"$gte": start, "$lte": end}},
    ).sort("date", 1))

    result = {}
    for doc in raw:
        code = doc["code"]
        date_str = doc["date"]
        result.setdefault(code, {})[date_str] = {
            "ma5": doc.get("ma5"),
            "ma10": doc.get("ma10"),
            "ma20": doc.get("ma20"),
            "ma60": doc.get("ma60"),
            "ma5_vol": doc.get("ma5_vol"),
            "high20": doc.get("high20"),
            "low20": doc.get("low20"),
            "rsi": doc.get("rsi"),
            "atr": doc.get("atr"),
            "adx": doc.get("adx"),
            "amplitude": doc.get("amplitude"),
        }

    return result
```

- [ ] **Step 2: Update `run_backtest` to load indicators**

After the line `stock_dfs = _load_aligned_klines(filtered, load_start, end_date)` (line 358), add:

```python
    indicators = _load_aligned_indicators(filtered, load_start, end_date)
    if task_id:
        total_ind = sum(len(v) for v in indicators.values())
        logging.info(f"[BACKTEST] 预计算指标已加载: {len(indicators)} 只股票, {total_ind} 条记录")
```

Then pass `precomputed_indicators` to the strategy. Modify the `cerebro.addstrategy` call (lines 397-404):

Old:
```python
    cerebro.addstrategy(PortfolioRuleStrategy,
                        stock_codes=codes_with_data,
                        name_map=name_map,
                        custom_rules=custom_rules,
                        max_positions=max_positions,
                        start_date_str=start_date,
                        task_id=task_id,
                        bars_total=bars_total)
```

New:
```python
    cerebro.addstrategy(PortfolioRuleStrategy,
                        stock_codes=codes_with_data,
                        name_map=name_map,
                        custom_rules=custom_rules,
                        max_positions=max_positions,
                        start_date_str=start_date,
                        task_id=task_id,
                        bars_total=bars_total,
                        precomputed_indicators=indicators)
```

- [ ] **Step 3: Add `precomputed_indicators` to strategy params**

Old `params` (lines 120-125):
```python
    params = dict(
        stock_codes=None, name_map=None, custom_rules=None,
        max_hold_days=60, cooldown_days=3, stop_loss_pct=0.08,
        max_positions=5, start_date_str=None,
        task_id=None, bars_total=0,
    )
```

New:
```python
    params = dict(
        stock_codes=None, name_map=None, custom_rules=None,
        max_hold_days=60, cooldown_days=3, stop_loss_pct=0.08,
        max_positions=5, start_date_str=None,
        task_id=None, bars_total=0,
        precomputed_indicators=None,
    )
```

- [ ] **Step 4: Update `__init__` to remove backtrader indicators**

Old (lines 129-167):
```python
    def __init__(self):
        from bin.rule_engine import StockRuleEngine

        self.codes = list(self.p.stock_codes) if self.p.stock_codes else []
        self.name_map = self.p.name_map or {}

        if self.p.custom_rules is not None:
            self.rules = self.p.custom_rules
        else:
            db = get_db()
            self.rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))

        self.engine = StockRuleEngine(self.rules) if self.rules else None

        self.indicators = {}
        for i, code in enumerate(self.codes):
            d = self.datas[i]
            self.indicators[code] = {
                'sma5': bt.indicators.SMA(d.close, period=5),
                'sma10': bt.indicators.SMA(d.close, period=10),
                'sma20': bt.indicators.SMA(d.close, period=20),
                'sma60': bt.indicators.SMA(d.close, period=60),
                'sma_vol5': bt.indicators.SMA(d.volume, period=5),
                'high20': bt.indicators.Highest(d.high, period=20),
                'low20': bt.indicators.Lowest(d.low, period=20),
                'rsi': bt.indicators.RSI_Safe(d.close, period=14),
                'atr': bt.indicators.ATR(d, period=14),
                'adx': bt.indicators.ADX(d, period=14),
            }

        raw = self.p.start_date_str
        self.start_date = pd.Timestamp(raw).date() if raw else None
        self.entry_prices = {}
        self.entry_dates = {}
        self.last_exit_dates = {}
        self.trade_log = []

        self._bar_count = 0
        self._bars_total = self.p.bars_total or 0
        self._next_progress_pct = 5
        self._code_index = {code: i for i, code in enumerate(self.codes)}
```

New:
```python
    def __init__(self):
        from bin.rule_engine import StockRuleEngine

        self.codes = list(self.p.stock_codes) if self.p.stock_codes else []
        self.name_map = self.p.name_map or {}

        if self.p.custom_rules is not None:
            self.rules = self.p.custom_rules
        else:
            db = get_db()
            self.rules = list(db.trading_rules.find({"enabled": True}).sort("rule_id", 1))

        self.engine = StockRuleEngine(self.rules) if self.rules else None

        self.precomputed = self.p.precomputed_indicators or {}
        if not self.precomputed:
            logging.warning("[BACKTEST] 无预计算指标数据，回测将使用默认值")

        raw = self.p.start_date_str
        self.start_date = pd.Timestamp(raw).date() if raw else None
        self.entry_prices = {}
        self.entry_dates = {}
        self.last_exit_dates = {}
        self.trade_log = []

        self._bar_count = 0
        self._bars_total = self.p.bars_total or 0
        self._next_progress_pct = 5
        self._code_index = {code: i for i, code in enumerate(self.codes)}
```

- [ ] **Step 5: Update `_ctx` to read from pre-computed dict**

Old (lines 169-187):
```python
    def _ctx(self, code, has_pos, cost, buy_date, today):
        from bin.rule_engine import StockRuleEngine
        d = self.datas[self._code_index[code]]
        ind = self.indicators[code]

        last_close = d.close[-1] if len(d) > 1 else d.close[0]
        amplitude = (d.high[0] - d.low[0]) / last_close if last_close > 0 else 0

        return StockRuleEngine.build_context({
            "close": d.close[0], "volume": d.volume[0],
            "ma5": ind['sma5'][0], "ma10": ind['sma10'][0],
            "ma20": ind['sma20'][0], "ma60": ind['sma60'][0],
            "ma5_vol": ind['sma_vol5'][0],
            "last_close": last_close,
            "high": ind['high20'][0], "low": ind['low20'][0],
            "open": d.open[0], "name": self.name_map.get(code, ""),
            "rsi": ind['rsi'][0], "atr": ind['atr'][0], "adx": ind['adx'][0],
            "amplitude": amplitude,
        }, {"has_pos": has_pos, "cost": cost, "buy_date": buy_date, "today": today})
```

New:
```python
    def _ctx(self, code, has_pos, cost, buy_date, today):
        from bin.rule_engine import StockRuleEngine
        d = self.datas[self._code_index[code]]

        date_str = d.datetime.date(0).isoformat()
        stock_ind = self.precomputed.get(code, {}).get(date_str, {})

        last_close = d.close[-1] if len(d) > 1 else d.close[0]
        amplitude = stock_ind.get("amplitude",
                                  (d.high[0] - d.low[0]) / last_close if last_close > 0 else 0)

        return StockRuleEngine.build_context({
            "close": d.close[0], "volume": d.volume[0],
            "ma5": stock_ind.get("ma5", d.close[0]),
            "ma10": stock_ind.get("ma10", d.close[0]),
            "ma20": stock_ind.get("ma20", d.close[0]),
            "ma60": stock_ind.get("ma60", d.close[0]),
            "ma5_vol": stock_ind.get("ma5_vol", d.volume[0]),
            "last_close": last_close,
            "high": stock_ind.get("high20", d.high[0]),
            "low": stock_ind.get("low20", d.low[0]),
            "open": d.open[0], "name": self.name_map.get(code, ""),
            "rsi": stock_ind.get("rsi", 50),
            "atr": stock_ind.get("atr", 0),
            "adx": stock_ind.get("adx", 25),
            "amplitude": amplitude,
        }, {"has_pos": has_pos, "cost": cost, "buy_date": buy_date, "today": today})
```

- [ ] **Step 6: Verify compilation**

```bash
cd D:\home\apps\api
python -c "import py_compile; py_compile.compile('services/backtest_engine.py', doraise=True)"
```

Expected: no error.

- [ ] **Step 7: Commit**

```bash
cd D:\home
git add apps/api/services/backtest_engine.py
git commit -m "feat: 回测引擎加载预计算指标，清除 backtrader indicator 创建"
```

---

## Task 6: Add scheduler config for daily indicator update

**Files:**
- Modify: `apps/api/config/inputs.conf`

- [ ] **Step 1: Add indicator update schedule**

Add a new section after the kline spider line:

```ini
[script://bin/indicator_calculator.py]
enable = true
cron=hour=15,minute=20
```

This runs the indicator calculator at 15:20 daily, 10 minutes after the kline spider (15:10).

- [ ] **Step 2: Commit**

```bash
cd D:\home
git add apps/api/config/inputs.conf
git commit -m "feat: 每日 15:20 自动计算指标"
```

---

## Task 7: [Manual] Run backfill

The backfill must be run manually once to populate all historical data.

- [ ] **Step 1: Run backfill from the scheduler host**

```bash
cd D:\home\apps\api
python bin/indicator_calculator.py backfill
```

Expected output:
```
回填指标: 共 ~5000 只股票
回填进度: 200/5000 (更新 150, 错误 0)
...
回填完成: 更新 5000 只, 错误 0 只
```

- [ ] **Step 2: Verify data exists**

```bash
cd D:\home\apps\api
python -c "from database import get_db; print(get_db().stock_indicators.count_documents({}))"
```

Expected: non-zero count (e.g., 5000 stocks × ~250 trading days = ~1.25M docs).

- [ ] **Step 3: Verify indicator values look correct**

```bash
cd D:\home\apps\api
python -c "
from database import get_db
db = get_db()
doc = db.stock_indicators.find_one()
print(doc)
"
```

Expected: a document with all indicator fields (code, date, ma5, ma10, ..., rsi, atr, adx, amplitude).

- [ ] **Step 4: Commit after manual verification**

```bash
cd D:\home
git add -A
git commit -m "feat: 回填全历史指标数据到 stock_indicators"
```
