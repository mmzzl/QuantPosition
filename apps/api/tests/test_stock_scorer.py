import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock

from services.stock_scorer import StockScorer


def test_score_basic_structure():
    with patch("services.stock_scorer.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = []

        scorer = StockScorer()
        result = scorer.score("600001", "TestCorp", "2026-07-10")
    assert result["code"] == "600001"
    assert "total" in result
    assert "level" in result
    assert "breakdown" in result
    assert isinstance(result["total"], (int, float))


def test_filtered_stock():
    scorer = StockScorer()
    result = scorer.score("300750", "宁德时代", "2026-07-10")
    assert result["total"] == 0

    result = scorer.score("688001", "某股票", "2026-07-10")
    assert result["total"] == 0


def test_st_stock():
    scorer = StockScorer()
    result = scorer.score("600001", "ST华业", "2026-07-10")
    assert result["total"] == 0


def test_score_level_classification():
    with patch("services.stock_scorer.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = []

        scorer = StockScorer()
        result = scorer.score("600001", "TestCorp", "2026-07-10")
    assert result["level"] == "C"


def test_default_date():
    with patch("services.stock_scorer.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = []

        scorer = StockScorer()
        result = scorer.score("600001", "Test")
    assert "date" in result
    assert result["date"] is not None


def _sample_score_result(total=55, level="A"):
    return {
        "code": "000001", "name": "平安银行", "date": "2026-07-10",
        "total": total, "level": level,
        "breakdown": {
            "price_volume": {"total": 20, "breakdown": {"vol_ratio": 10, "trend": 10}},
            "fund_chip": {"total": 8, "breakdown": {"fund_flow": 5, "chip": 3}},
            "sector_theme": {"total": 15, "breakdown": {"hotness": 10, "sector": 5}},
            "risk": {"total": 2, "breakdown": {"pe": 1, "risk_flag": 1}},
        },
    }


def test_unify_output_structure():
    intention_info = {
        "intention": "吸筹", "bonus": 15, "confidence": "高", "detail": "主力吸筹明显",
    }
    result = StockScorer.unify(_sample_score_result(), intention_info,
                               conclusion="买入", strategy="持有")

    assert result["code"] == "000001"
    assert result["name"] == "平安银行"
    assert result["date"] == "2026-07-10"
    for dim in ["price_volume", "fund_chip", "sector_theme", "risk"]:
        assert dim in result["dimensions"]
        assert "score" in result["dimensions"][dim]
        assert "max" in result["dimensions"][dim]
        assert "detail" in result["dimensions"][dim]
    assert result["dimensions"]["price_volume"]["max"] == 40
    assert result["dimensions"]["fund_chip"]["max"] == 13
    assert result["dimensions"]["sector_theme"]["max"] == 20
    assert result["dimensions"]["risk"]["max"] == 5
    assert result["dimensions"]["price_volume"]["detail"] == {"vol_ratio": 10, "trend": 10}
    assert result["quantitative_score"] == 55
    assert result["quantitative_level"] == "A"
    assert result["main_force_intention"] == "吸筹"
    assert result["intention_bonus"] == 15
    assert result["intention_confidence"] == "高"
    assert result["intention_detail"] == "主力吸筹明显"
    assert result["conclusion"] == "买入"
    assert result["strategy"] == "持有"
    assert result["total_score"] == 70
    assert result["grade"] == "A"


def test_unify_no_intention():
    result = StockScorer.unify(_sample_score_result())
    assert result["quantitative_score"] == 55
    assert result["main_force_intention"] == ""
    assert result["intention_bonus"] == 0
    assert result["intention_confidence"] == ""
    assert result["intention_detail"] == ""
    assert result["total_score"] == 55
    assert result["grade"] == "B"


def test_unify_clamp_score():
    result = StockScorer.unify(
        _sample_score_result(total=95, level="S"),
        {"intention": "吸筹", "bonus": 999, "confidence": "高", "detail": ""},
    )
    assert result["total_score"] == 100
    assert result["grade"] == "S"

    result = StockScorer.unify(_sample_score_result(total=-50, level="C"))
    assert result["total_score"] == 0
    assert result["grade"] == "C"


def test_unify_true_distribution():
    result = StockScorer.unify(
        _sample_score_result(total=85, level="S"),
        {"intention": "真出货", "bonus": -999, "confidence": "高", "detail": "主力真出货"},
    )
    assert result["total_score"] == 0
    assert result["grade"] == "C"
    assert result["intention_bonus"] == -999
