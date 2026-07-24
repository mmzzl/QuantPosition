import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from datetime import datetime
from services.heatmap_selection_service import HeatmapSelectionService


class TestRunHeatmapSelection:

    def test_run_heatmap_selection_returns_task_id(self):
        mock_task = MagicMock()
        mock_task.id = "heatmap-task-789"
        with patch("tasks.heatmap_selection_tasks.run_heatmap_selection.delay", return_value=mock_task):
            task_id = HeatmapSelectionService.run_heatmap_selection()
        assert task_id == "heatmap-task-789"

    def test_run_heatmap_selection_calls_delay(self):
        mock_task = MagicMock()
        mock_task.id = "tid"
        with patch("tasks.heatmap_selection_tasks.run_heatmap_selection.delay", return_value=mock_task) as mock_delay:
            HeatmapSelectionService.run_heatmap_selection()
        mock_delay.assert_called_once_with()


class TestGetHeatmapSelection:

    def test_returns_empty_when_no_data(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.heatmap_selection_cache = mock_cache
        mock_cache.aggregate.return_value = []

        with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
            result = HeatmapSelectionService.get_heatmap_selection()

        assert len(result["sectors"]) == 0
        assert len(result["stocks"]) == 0
        assert result["total"] == 0

    def test_stock_item_has_heatmap_score_and_grade(self):
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

    def test_scoring_rules(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.heatmap_selection_cache = mock_cache

        mock_cache.aggregate.return_value = [
            {"_id": "科技", "avg_change_pct": 5.0, "stock_count": 50}
        ]
        mock_cache.find.return_value = [
            {
                "code": "300001", "name": "科技龙头",
                "sector_name": "科技",
                "current_price": 25.0, "open_price": 23.0,
                "change_pct": 8.0, "volume": 200_000_000,
                "amount": 5_000_000_000,
                "sector_rank": 2, "sector_rank_pct": 4,
            }
        ]

        with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
            result = HeatmapSelectionService.get_heatmap_selection()

        stock = result["stocks"][0]
        assert stock["score"] >= 80
        assert "板块龙头" in stock["flags"]
        assert "巨量活跃" in stock["flags"]
        assert "中高价" in stock["flags"]
        assert "强势" in stock["flags"]

    def test_top_n_limits_sectors(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.heatmap_selection_cache = mock_cache

        mock_cache.aggregate.return_value = [
            {"_id": "A", "avg_change_pct": 3.0, "stock_count": 10},
            {"_id": "B", "avg_change_pct": 2.0, "stock_count": 10},
        ]

        with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
            result = HeatmapSelectionService.get_heatmap_selection(top_n=1)

        assert len(result["sectors"]) <= 1

    def test_supports_date_filter(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.heatmap_selection_cache = mock_cache
        mock_cache.aggregate.return_value = []

        with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
            HeatmapSelectionService.get_heatmap_selection(
                start_date="2026-07-01", end_date="2026-07-24"
            )

        args, _ = mock_cache.aggregate.call_args
        pipeline = args[0]
        match_stage = pipeline[0]
        assert "$gte" in match_stage["$match"]["created_at"]
        assert "$lte" in match_stage["$match"]["created_at"]

    def test_pagination(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.heatmap_selection_cache = mock_cache

        mock_cache.aggregate.return_value = [
            {"_id": "银行", "avg_change_pct": 2.5, "stock_count": 30}
        ]
        mock_cache.find.return_value = [
            {
                "code": f"000{i:03d}", "name": f"股票{i}",
                "sector_name": "银行",
                "current_price": 10.0 + i, "open_price": 10.0,
                "change_pct": 1.0, "volume": 1_000_000,
                "amount": 10_000_000,
                "sector_rank": i, "sector_rank_pct": i * 10,
            }
            for i in range(1, 11)
        ]

        with patch("services.heatmap_selection_service.get_db", return_value=mock_db):
            p1 = HeatmapSelectionService.get_heatmap_selection(page=1, page_size=3)
            p2 = HeatmapSelectionService.get_heatmap_selection(page=2, page_size=3)

        assert len(p1["stocks"]) == 3
        assert len(p2["stocks"]) == 3
        assert p1["page"] == 1
        assert p2["page"] == 2
        assert p1["stocks"][0]["code"] != p2["stocks"][0]["code"]
