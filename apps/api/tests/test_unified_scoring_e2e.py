import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from services.stock_scorer import StockScorer
from services.review_service import ReviewService
from bin.review_picker import calc_score


BASE_SCORE_RESULT = {
    "code": "000001", "name": "平安银行", "date": "2026-07-10",
    "total": 55, "level": "A",
    "breakdown": {
        "price_volume": {"total": 20, "breakdown": {"vol_ratio": 10, "trend": 10}},
        "fund_chip": {"total": 8, "breakdown": {"fund_flow": 5, "chip": 3}},
        "sector_theme": {"total": 15, "breakdown": {"hotness": 10, "sector": 5}},
        "risk": {"total": 2, "breakdown": {"pe": 1, "risk_flag": 1}},
    },
}

INTENTION_MAP = {
    "吸筹": 15, "洗盘": 10, "假出货诱空": 10,
    "高位震荡": 0, "出货风险": -50, "真出货": -999, "震荡": 0,
}


def make_daily_kline(dates, closes, volumes=None):
    vols = volumes if volumes else [100000] * len(closes)
    klines = []
    for i, (d, c) in enumerate(zip(dates, closes)):
        open_p = closes[i - 1] if i > 0 else c
        klines.append({
            "date": d, "open": open_p, "close": c,
            "high": max(open_p, c) * 1.02, "low": min(open_p, c) * 0.98,
            "volume": vols[i] if i < len(vols) else 100000,
        })
    return klines


def make_bar(t, o, c, v):
    return {"date": f"2026-07-17 {t}", "open": o, "close": c,
            "high": max(o, c) * 1.01, "low": min(o, c) * 0.99,
            "volume": v, "amount": v * c}


# ── TC-001: score() + unify() 全链路 ──

def test_tc_001_score_unify_end_to_end():
    with patch("services.stock_scorer.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = []

        scorer = StockScorer()
        score_result = scorer.score("600001", "TestCorp", "2026-07-10")

    assert "total" in score_result
    assert "breakdown" in score_result
    assert "level" in score_result

    intention_info = {"intention": "吸筹", "bonus": 15, "confidence": "高", "detail": "主力吸筹"}
    unified = StockScorer.unify(score_result, intention_info, conclusion="持有", strategy="中线持有")

    assert unified["code"] == "600001"
    assert "dimensions" in unified
    assert "quantitative_score" in unified
    assert "quantitative_level" in unified
    assert "grade" in unified
    assert "total_score" in unified
    for dim_key in ("price_volume", "fund_chip", "sector_theme", "risk"):
        d = unified["dimensions"][dim_key]
        assert "score" in d
        assert "max" in d
        assert "detail" in d


# ── TC-002: analyze() 统一结构 ──

def test_tc_002_analyze_unified_structure():
    with patch("services.stock_scorer.get_db") as mock_get_db, \
         patch("services.review_service.ReviewService._get_daily_klines") as mock_daily, \
         patch("services.review_service.ReviewService._get_5m_klines") as mock_5m:
        mock_get_db.return_value = MagicMock()
        mock_daily.return_value = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(20)],
            [10.0 + i * 0.05 for i in range(20)],
        )
        mock_5m.return_value = [
            make_bar("09:35", 10.0, 10.05, 10000),
            make_bar("09:40", 10.05, 10.10, 15000),
        ]
        result = ReviewService.analyze("000001", "平安银行", "2026-07-17")

    assert "dimensions" in result
    assert "quantitative_score" in result
    assert "total_score" in result
    assert "grade" in result
    assert "position" in result
    assert "vwap_status" in result
    assert "volume_signal" in result
    assert "pattern" in result
    assert "tail_signal" in result
    assert "main_force_intention" in result
    assert "conclusion" in result
    assert isinstance(result["total_score"], int)


# ── TC-003: calc_score 读取 total_score ──

def test_tc_003_calc_score_reads_total_score():
    r = {"code": "000001", "name": "平安银行", "conclusion": "持有", "total_score": 85, "grade": "S"}
    assert calc_score(r) == 85


# ── TC-004: 真出货 → total_score=0 ──

def test_tc_004_true_distribution_forces_zero():
    result = StockScorer.unify(
        {**BASE_SCORE_RESULT, "total": 85, "level": "S"},
        {"intention": "真出货", "bonus": -999, "confidence": "高", "detail": "高位出货"},
    )
    assert result["total_score"] == 0
    assert result["grade"] == "C"


# ── TC-005: 无 intention_info 兜底 ──

def test_tc_005_unify_no_intention():
    result = StockScorer.unify({**BASE_SCORE_RESULT, "total": 45, "level": "B"})
    assert result["main_force_intention"] == ""
    assert result["intention_bonus"] == 0
    assert result["intention_confidence"] == ""
    assert result["intention_detail"] == ""
    assert result["total_score"] == 45


# ── TC-006: Score clamp [0, 100] ──

def test_tc_006_score_clamp_upper():
    result = StockScorer.unify(
        {**BASE_SCORE_RESULT, "total": 95, "level": "S"},
        {"intention": "吸筹", "bonus": 999, "confidence": "高", "detail": ""},
    )
    assert result["total_score"] == 100
    assert result["grade"] == "S"


def test_tc_006_score_clamp_lower():
    result = StockScorer.unify({**BASE_SCORE_RESULT, "total": -50, "level": "C"})
    assert result["total_score"] == 0
    assert result["grade"] == "C"


# ── TC-007: analyze() 跳过路径 ──

def test_tc_007_skip_no_5m_data():
    with patch("services.stock_scorer.get_db") as mock_get_db, \
         patch("services.review_service.ReviewService._get_daily_klines") as mock_daily, \
         patch("services.review_service.ReviewService._get_5m_klines") as mock_5m:
        mock_get_db.return_value = MagicMock()
        mock_daily.return_value = make_daily_kline(
            [f"2026-07-{i+1:02d}" for i in range(20)],
            [10.0 for _ in range(20)],
        )
        mock_5m.return_value = []
        result = ReviewService.analyze("000001", "平安银行", "2026-07-17")

    assert result["total_score"] == 0
    assert result["grade"] == "C"
    assert result["conclusion"] == "跳过"
    assert "strategy" in result


# ── TC-008: calc_score 过滤非持有 ──

def test_tc_008_calc_score_filters_non_hold():
    assert calc_score({"conclusion": "卖出", "total_score": 80}) == -1
    assert calc_score({"conclusion": "观望", "total_score": 80}) == -1
    assert calc_score({"conclusion": "", "total_score": 80}) == -1


# ── TC-009: heatmap_selection 输出对齐 ──

def test_tc_009_heatmap_has_score_and_grade():
    from services.heatmap_selection_service import HeatmapSelectionService

    mock_db = MagicMock()
    mock_cache = MagicMock()
    mock_db.heatmap_selection_cache = mock_cache
    mock_cache.aggregate.return_value = [
        {"_id": "银行", "avg_change_pct": 2.5, "stock_count": 30},
    ]
    mock_cache.find.return_value = [{
        "code": "000001", "name": "平安银行", "sector_name": "银行",
        "current_price": 12.5, "open_price": 12.3,
        "change_pct": 1.6, "volume": 100_000_000, "amount": 1_250_000_000,
        "sector_rank": 1, "sector_rank_pct": 5,
    }]

    with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
        result = HeatmapSelectionService.get_heatmap_selection()

    stock = result["stocks"][0]
    assert "heatmap_score" in stock
    assert stock["heatmap_score"] == stock["score"]
    assert "grade" in stock
    assert stock["grade"] in ("S", "A", "B", "C")


# ── TC-010: INTENTION_BONUS 完整性 ──

def test_tc_010_intention_bonus_completeness():
    expected_keys = {"吸筹", "洗盘", "假出货诱空", "高位震荡", "出货风险", "真出货", "震荡"}
    assert set(StockScorer.INTENTION_BONUS.keys()) == expected_keys
    for intention, expected_bonus in INTENTION_MAP.items():
        assert StockScorer.INTENTION_BONUS[intention] == expected_bonus, (
            f"{intention}: expected {expected_bonus}, got {StockScorer.INTENTION_BONUS[intention]}"
        )
