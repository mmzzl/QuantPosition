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
