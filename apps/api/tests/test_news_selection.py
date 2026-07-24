import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from datetime import datetime
from services.news_selection_service import NewsSelectionService


class TestRunNewsSelection:

    def test_run_news_selection_returns_task_id(self):
        mock_task = MagicMock()
        mock_task.id = "news-task-456"
        with patch("tasks.news_selection_tasks.run_news_selection.delay", return_value=mock_task):
            task_id = NewsSelectionService.run_news_selection()
        assert task_id == "news-task-456"

    def test_run_news_selection_calls_delay(self):
        mock_task = MagicMock()
        mock_task.id = "tid"
        with patch("tasks.news_selection_tasks.run_news_selection.delay", return_value=mock_task) as mock_delay:
            NewsSelectionService.run_news_selection()
        mock_delay.assert_called_once_with()


class TestGetNewsStocks:

    def test_returns_empty_when_no_data(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.news_selection_cache = mock_cache
        mock_cache.count_documents.return_value = 0
        mock_cache.find.return_value.sort.return_value.skip.return_value.limit.return_value = []

        with patch("services.news_selection_service.get_db", return_value=mock_db):
            result = NewsSelectionService.get_news_stocks()

        assert result["total"] == 0
        assert result["stocks"] == []

    def test_returns_paginated_stocks(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.news_selection_cache = mock_cache
        mock_cache.count_documents.return_value = 1
        mock_cache.find.return_value.sort.return_value.skip.return_value.limit.return_value = [
            {
                "code": "000001", "name": "平安银行",
                "bk_code": "BK001", "bk_name": "银行",
                "news_titles": ["利好"], "news_times": ["2026-07-24 10:00"],
                "current_price": 12.5, "target_price": 15.0,
                "stop_loss": 11.0, "expected_return": 20.0,
                "risk": 12.0, "ma_signal": "golden_cross",
                "created_at": datetime(2026, 7, 24)
            }
        ]

        with patch("services.news_selection_service.get_db", return_value=mock_db):
            result = NewsSelectionService.get_news_stocks(page=1, page_size=10)

        assert result["total"] == 1
        assert len(result["stocks"]) == 1
        assert result["stocks"][0]["code"] == "000001"
        assert result["stocks"][0]["ma_signal"] == "golden_cross"
        assert result["page"] == 1
        assert result["page_size"] == 10

    def test_supports_date_filter(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.news_selection_cache = mock_cache
        mock_cache.count_documents.return_value = 0
        mock_cache.find.return_value.sort.return_value.skip.return_value.limit.return_value = []

        with patch("services.news_selection_service.get_db", return_value=mock_db):
            NewsSelectionService.get_news_stocks(start_date="2026-07-01", end_date="2026-07-24")

        args, _ = mock_cache.count_documents.call_args
        assert "$gte" in args[0].get("created_at", {})
        assert "$lte" in args[0].get("created_at", {})

    def test_supports_period_filter(self):
        mock_db = MagicMock()
        mock_cache = MagicMock()
        mock_db.news_selection_cache = mock_cache
        mock_cache.count_documents.return_value = 0
        mock_cache.find.return_value.sort.return_value.skip.return_value.limit.return_value = []

        with patch("services.news_selection_service.get_db", return_value=mock_db):
            NewsSelectionService.get_news_stocks(period="7d")

        args, _ = mock_cache.count_documents.call_args
        assert "$gte" in args[0].get("created_at", {})
