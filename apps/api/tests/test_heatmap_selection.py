import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from services.heatmap_selection_service import HeatmapSelectionService


def test_stock_item_has_heatmap_score_and_grade():
    mock_db = MagicMock()
    mock_cache = MagicMock()
    mock_db.heatmap_selection_cache = mock_cache

    mock_cache.aggregate.return_value = [
        {"_id": "银行", "avg_change_pct": 2.5, "stock_count": 30}
    ]
    mock_cache.find.return_value = [
        {
            "code": "000001", "name": "平安银行",
            "sector_name": "银行",
            "current_price": 12.5, "open_price": 12.3,
            "change_pct": 1.6, "volume": 100_000_000,
            "amount": 1_250_000_000,
            "sector_rank": 1, "sector_rank_pct": 5,
        }
    ]

    with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
        result = HeatmapSelectionService.get_heatmap_selection()

    assert len(result["stocks"]) == 1
    stock = result["stocks"][0]
    assert "heatmap_score" in stock
    assert stock["heatmap_score"] == stock["score"]
    assert "grade" in stock
    assert stock["grade"] in ("S", "A", "B", "C")
