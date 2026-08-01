# Unified Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or inline execution.

**Goal:** Unify 5 scattered scoring systems into a single output structure: quantitative 4-dimensions + main force intention + qualitative conclusion.

**Architecture:** StockScorer retains its 4-dimension quantitative engine (backward compatible). ReviewService.analyze() becomes the single entry point for the unified structure, calling StockScorer internally and adding intention/conclusion. All consumers (review_picker, rule_engine, backtest) read from the same structure.

**Output structure (all scoring goes through this):**

```python
{
    "code": "000001", "name": "平安银行", "date": "2026-07-17",
    # 量化4维
    "dimensions": {
        "price_volume": {"score": 32, "max": 40, "detail": "..."},
        "fund_chip":     {"score": 10, "max": 13, "detail": "..."},
        "sector_theme":  {"score": 15, "max": 20, "detail": "..."},
        "risk":          {"score": 5,  "max": 5,  "detail": "..."},
    },
    "quantitative_score": 62,      # 0-78
    "quantitative_level": "A",      # S≥60 / A≥45 / B≥30 / C<30 (独立于意图)
    # 主力意图（第5维）
    "main_force_intention": "吸筹",
    "intention_bonus": 15,
    "intention_confidence": "高",
    "intention_detail": "低位+上涨放量下跌缩量，持续量堆，底部形态",
    # 定性结论
    "conclusion": "持有",
    "strategy": "中线看好，缩量回调可加仓，放量滞涨再减仓",
    # 综合
    "total_score": 77,              # quantitative + bonus, clamp 0-100
    "grade": "B",                   # S≥80 / A≥60 / B≥40 / C<40
    # 盘口（ReviewService 特有）
    "position": "低位", "vwap_status": "强势",
    "volume_signal": "洗盘", "pattern": "U型洗盘分时", "tail_signal": "抢筹",
}
```

**Consumers of the unified structure:**
- `StockScorer.score()` → returns `{total, level, breakdown}` (existing, unchanged)
- `ReviewService.analyze()` → returns the full unified structure above
- `review_picker.py` → reads `total_score` + `conclusion` from analyze() result
- `rule_engine.py` → reads `total` from StockScorer.score() (no change, no 5-min data)
- `backtest_engine.py` → reads `total` from StockScorer.score() (no change)
- `heatmap_selection_service.py` → keeps its own score but output format aligns

**Grade mapping (unified total_score, max 93):**
- S ≥ 80
- A ≥ 60
- B ≥ 40
- C < 40

**Intention bonus values:**
| 意图 | bonus |
|------|-------|
| 吸筹 | +15 |
| 洗盘 | +10 |
| 假出货诱空 | +10 |
| 高位震荡 | 0 |
| 出货风险 | -50 |
| 真出货 | -999 |
| 震荡 | 0 |

**Tech Stack:** Python 3.12, no new dependencies.

---

### Task 1: Add `unify()` class method to StockScorer

**Files:**
- Modify: `services/stock_scorer.py` (after line 117, before `return`)
- Test: `tests/test_stock_scorer.py` (append)

This is a formatting transformation: takes the existing score result + optional intention info, produces the unified structure.

- [ ] **Step 1: Write the test**

```python
# tests/test_stock_scorer.py (append)

def test_unify_output_structure():
    mock_quant = {
        "code": "000001", "name": "平安银行", "date": "2026-07-17",
        "total": 40, "level": "B",
        "breakdown": {
            "price_volume": {"total": 20, "breakdown": {"trend": 10, "volume": 10}},
            "fund_chip": {"total": 8, "breakdown": {"concentration": 5, "turnover": 3}},
            "sector_theme": {"total": 10, "breakdown": {"rank": 6, "return": 4}},
            "risk": {"total": 2, "breakdown": {"st": 2, "delist": 0, "announcement": 0}},
        }
    }
    intention = {
        "intention": "吸筹", "bonus": 15, "confidence": "高",
        "detail": "低位建仓",
    }
    result = StockScorer.unify(mock_quant, intention, "持有", "中线持有")

    assert result["code"] == "000001"
    assert result["quantitative_score"] == 40
    assert result["dimensions"]["price_volume"]["score"] == 20
    assert result["dimensions"]["risk"]["score"] == 2
    assert result["main_force_intention"] == "吸筹"
    assert result["intention_bonus"] == 15
    assert result["total_score"] == 55  # 40 + 15
    assert result["grade"] == "B"       # 55 >= 40
    assert result["conclusion"] == "持有"


def test_unify_no_intention():
    """rule_engine/backtest场景：只有量化分，没有意图"""
    mock_quant = {"code": "000001", "name": "Test", "date": "2026-07-17",
                  "total": 62, "level": "A", "breakdown": {}}
    result = StockScorer.unify(mock_quant)

    assert result["quantitative_score"] == 62
    assert result["total_score"] == 62
    assert result["main_force_intention"] == ""
    assert result["intention_bonus"] == 0
    assert result["grade"] == "A"
    assert result["conclusion"] == "观望"


def test_unify_clamp_score():
    """total_score clamp 0-100"""
    mock_quant = {"code": "000001", "name": "Test", "date": "2026-07-17",
                  "total": 90, "level": "S", "breakdown": {}}
    intention = {"intention": "吸筹", "bonus": 15, "confidence": "高", "detail": ""}
    result = StockScorer.unify(mock_quant, intention, "持有", "")
    assert result["total_score"] == 100  # 90+15=105 → clamp 100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:\home\apps\api
python -m pytest tests/test_stock_scorer.py::test_unify_output_structure -v
```

Expected: FAIL with `AttributeError: type object 'StockScorer' has no attribute 'unify'`

- [ ] **Step 3: Add `unify()` and `_calc_grade()` to StockScorer**

```python
# services/stock_scorer.py — add after score() method (before class end)

INTENTION_BONUS = {
    "吸筹": 15,
    "洗盘": 10,
    "假出货诱空": 10,
    "高位震荡": 0,
    "出货风险": -50,
    "真出货": -999,
    "震荡": 0,
}

@staticmethod
def _calc_grade(total_score: int) -> str:
    if total_score >= 80:
        return "S"
    elif total_score >= 60:
        return "A"
    elif total_score >= 40:
        return "B"
    return "C"

@staticmethod
def _build_dimensions(breakdown: dict) -> dict:
    dims = {}
    for key, val in breakdown.items():
        dims[key] = {
            "score": val.get("total", 0),
            "max": {"price_volume": 40, "fund_chip": 13, "sector_theme": 20, "risk": 5}.get(key, 0),
            "detail": val.get("breakdown", {}),
        }
    return dims

@classmethod
def unify(cls, score_result: dict,
          intention_info: Optional[dict] = None,
          conclusion: str = "观望",
          strategy: str = "") -> dict:
    quantitative = score_result.get("total", 0)
    breakdown = score_result.get("breakdown", {})

    intention = (intention_info or {}).get("intention", "")
    bonus = cls.INTENTION_BONUS.get(intention, 0) if intention else 0
    raw_total = quantitative + max(bonus, 0)
    total_score = max(0, min(100, raw_total))

    result = {
        "code": score_result.get("code", ""),
        "name": score_result.get("name", ""),
        "date": score_result.get("date", ""),
        "dimensions": cls._build_dimensions(breakdown),
        "quantitative_score": quantitative,
        "quantitative_level": score_result.get("level", "C"),
        "main_force_intention": intention,
        "intention_bonus": bonus,
        "intention_confidence": (intention_info or {}).get("confidence", ""),
        "intention_detail": (intention_info or {}).get("detail", ""),
        "conclusion": conclusion,
        "strategy": strategy,
        "total_score": total_score,
        "grade": cls._calc_grade(total_score),
    }

    if intention == "真出货":
        result["total_score"] = 0
        result["grade"] = "C"

    return result
```

- [ ] **Step 4: Run test**

```bash
cd D:\home\apps\api
python -m pytest tests/test_stock_scorer.py::test_unify_output_structure tests/test_stock_scorer.py::test_unify_no_intention tests/test_stock_scorer.py::test_unify_clamp_score -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd D:\home\apps\api
git add services/stock_scorer.py tests/test_stock_scorer.py
git commit -m "feat(scorer): add StockScorer.unify() for unified scoring output"
```

---

### Task 2: ReviewService.analyze() uses StockScorer.unify()

**Files:**
- Modify: `services/review_service.py:572-622` (the `analyze()` method)
- Test: `tests/test_review_service.py` (append new test class)

- [ ] **Step 1: Write the test**

```python
# tests/test_review_service.py (append)

class TestUnifiedOutput:
    def test_analyze_unified_structure(self):
        result = ReviewService.analyze("000001", "平安银行")
        assert "quantitative_score" in result
        assert "dimensions" in result
        assert "main_force_intention" in result
        assert "intention_bonus" in result
        assert "total_score" in result
        assert "grade" in result
        assert result["code"] == "000001"

    def test_skip_no_5m_data(self):
        result = ReviewService.analyze("000001", "平安银行")
        if result["conclusion"] == "跳过":
            assert result["total_score"] == 0
            assert result["grade"] == "C"
```

Note: this test hits the real DB so it may return "跳过" with no 5-min data.
That's fine — test is for structure only when data exists, and default values when skipping.

- [ ] **Step 2: Run test to confirm old structure still works (test will fail until we implement)**

```bash
cd D:\home\apps\api
python -m pytest tests/test_review_service.py::TestUnifiedOutput -v
```

- [ ] **Step 3: Rewrite `analyze()` to use StockScorer.unify()**

```python
# services/review_service.py — replace the analyze() method (lines 572-622)

@staticmethod
def analyze(code: str, name: str, date_str: str = None) -> Dict[str, Any]:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    daily_klines = ReviewService._get_daily_klines(code)
    bars_5m = ReviewService._get_5m_klines(code, date_str)
    if not bars_5m:
        scorer = StockScorer()
        quant = scorer.score(code, name, date_str)
        return StockScorer.unify(quant, conclusion="跳过",
                                 strategy=f"{date_str} 无5分钟K线数据")

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

    main_force = ReviewService._assess_main_force_intention(
        position, daily_klines, vwap_status, volume_signal, pattern, tail_signal
    )
    conclusion = ReviewService._generate_conclusion(
        position, vwap_status, volume_signal, pattern, tail_signal, main_force
    )

    scorer = StockScorer()
    quant = scorer.score(code, name, date_str)

    intention_info = {
        "intention": main_force["intention"],
        "bonus": StockScorer.INTENTION_BONUS.get(main_force["intention"], 0),
        "confidence": main_force["intention_confidence"],
        "detail": main_force["intention_detail"],
    }

    unified = StockScorer.unify(
        quant, intention_info,
        conclusion=conclusion["conclusion"],
        strategy=conclusion["strategy"],
    )
    unified["position"] = position
    unified["vwap_status"] = vwap_status
    unified["volume_signal"] = volume_signal
    unified["volume_detail"] = vol_detail
    unified["pattern"] = pattern
    unified["tail_signal"] = tail_signal
    unified["daily_vol_pattern"] = main_force["daily_vol_pattern"]
    unified["daily_patterns"] = main_force["daily_patterns"]

    return unified
```

- [ ] **Step 4: Run tests**

```bash
cd D:\home\apps\api
python -m pytest tests/test_review_service.py -v
```

Expected: 27 PASS (existing tests still pass, new tests pass or correctly skip)

- [ ] **Step 5: Commit**

```bash
cd D:\home\apps\api
git add services/review_service.py tests/test_review_service.py
git commit -m "feat(review): integrate StockScorer.unify() into analyze() output"
```

---

### Task 3: Simplify review_picker.py to use unified output

**Files:**
- Modify: `bin/review_picker.py`

Remove `calc_score()`, `INTENTION_BONUS` (moved to StockScorer), and all manual bonus logic.
`build_message()` reads `total_score` and `grade` directly from analyze() result.

- [ ] **Step 1: Write the test for review_picker message formatting**

No unit test for the script. Verify manually by dry-run with 1 stock.

- [ ] **Step 2: Modify review_picker.py**

```python
# Replace INTENTION_BONUS dict (lines 37-45) — DELETE entirely

# Keep INTENTION_ICON (lines 47-53) — KEEP (formatting only)

# Replace calc_score (lines 56-71) — DELETE entirely

# Replace build_message (lines 74-105) — simplified version:

def build_message(results: List[Dict]) -> tuple:
    scored = [(r.get("total_score", -1), r) for r in results if r.get("total_score", -1) >= 0]
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
        f"\U0001f4c8 综合评分：**{top_s:.0f}分** (等级{top_r.get('grade', 'C')})",
        top_r.get("intention_detail", ""),
        f"\U0001f4cc 日线定位：{top_r.get('position', '')}  |  日线量能：{top_r.get('daily_vol_pattern', '')}",
        f"\U0001f4ca 均价分析：{top_r.get('vwap_status', '')}  |  量能信号：{top_r.get('volume_signal', '')}",
        f"\U0001f50e 分时形态：{top_r.get('pattern', '')}  |  尾盘：{top_r.get('tail_signal', '')}",
        "",
        f"\u23f0 {top_r.get('strategy', '')}",
        "---",
        f"\U0001f50d 共评分 {len(scored)} 只 第1名 | 量化分{top_r.get('quantitative_score', 0)} | 意图置信度：{confidence}",
    ]
    title = f"明日关注 ({top_r['code']} {intention})"
    return title, "\n".join(lines)
```

Also simplify `main()`: remove the `calc_score(r)` calls and use `total_score` directly.

```python
# In main() — replace lines 128-147:
for i, future in enumerate(as_completed(futures)):
    stk = futures[future]
    try:
        r = future.result()
        with results_lock:
            results.append(r)
        logging.debug(f"Scored {stk['code']} {stk['name']}: {r.get('total_score', -1):.0f}")
    except Exception as e:
        logging.error(f"Error analyzing {stk['code']} {stk['name']}: {e}")

    if (i + 1) % 500 == 0:
        logging.info(f"Progress: {i+1}/{total}")

scored = sorted(
    [(r.get("total_score", -1), r) for r in results if r.get("total_score", -1) >= 0],
    key=lambda x: x[0], reverse=True
)
logging.info(f"Scored {len(scored)} stocks, top 5: {[(r['code'], int(s)) for s, r in scored[:5]]}")
```

- [ ] **Step 3: Run existing tests**

```bash
cd D:\home\apps\api
python -m pytest tests/ -v
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
cd D:\home\apps\api
git add bin/review_picker.py
git commit -m "refactor(review_picker): use unified total_score from ReviewService.analyze()"
```

---

### Task 4: Align heatmap_selection_service.py output

**Files:**
- Modify: `services/heatmap_selection_service.py`

The HeatmapSelectionService's `get_heatmap_selection()` returns its own scored dicts.
Align the output format to include `total_score` and `grade` fields for consistency.

- [ ] **Step 1: Read current output format**

```bash
cd D:\home\apps\api
grep -n "def get_heatmap_selection" services/heatmap_selection_service.py
```

- [ ] **Step 2: Modify the output to include total_score**

In `get_heatmap_selection()`, after computing `score`, add:

```python
# Add to the returned dict per stock:
item["total_score"] = score
item["grade"] = "S" if score >= 80 else "A" if score >= 60 else "B" if score >= 40 else "C"
```

- [ ] **Step 3: Run tests**

```bash
cd D:\home\apps\api
python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
cd D:\home\apps\api
git add services/heatmap_selection_service.py
git commit -m "refactor(heatmap): add total_score and grade to output for consistency"
```

---

## Self-Review

1. **Spec coverage:** Every requirement is covered — Task 1 adds the unified format, Task 2 integrates it into analyze(), Task 3 removes the ad-hoc double-scoring in review_picker, Task 4 aligns heatmap output.

2. **Placeholder scan:** No placeholders. All code is complete. All file paths are exact.

3. **Type consistency:** `unify()` signature matches in Task 1 and Task 2. `INTENTION_BONUS` is defined in StockScorer (Task 1) and imported by reference in Task 2. `total_score` field name is consistent across all tasks.
