import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from datetime import datetime
from services.selection_service import StockSelectionService


def make_kline(code, date, close, volume=100000, amount=None):
    o = close * 0.99
    h = close * 1.02
    lv = close * 0.98
    a = amount if amount is not None else volume * close
    return {"code": code, "date": date, "open": o, "close": close,
            "high": h, "low": lv, "volume": volume, "amount": a, "frequency": 9}


class TestRunDualMa:

    def test_run_dual_ma_returns_task_id(self):
        mock_task = MagicMock()
        mock_task.id = "test-task-id-123"
        with patch("tasks.selection_tasks.run_dual_ma_selection.delay", return_value=mock_task):
            task_id = StockSelectionService.run_dual_ma(short_period=5, long_period=20)
        assert task_id == "test-task-id-123"

    def test_run_dual_ma_forwards_params(self):
        mock_task = MagicMock()
        mock_task.id = "tid"
        with patch("tasks.selection_tasks.run_dual_ma_selection.delay", return_value=mock_task) as mock_delay:
            StockSelectionService.run_dual_ma(short_period=10, long_period=30)
        mock_delay.assert_called_once_with(short_period=10, long_period=30)

    def test_save_selection_result_inserts_one(self):
        mock_coll = MagicMock()
        result = {"code": "000001", "strategy": "dual_moving_average"}
        StockSelectionService.save_selection_result(mock_coll, result)
        mock_coll.insert_one.assert_called_once()


class TestDualMaSelection:

    def test_detects_golden_cross(self):
        mock_db = MagicMock()
        mock_kline = MagicMock()
        mock_selection = MagicMock()
        mock_db.stock_kline = mock_kline
        mock_db.stock_selections = mock_selection
        mock_db.sector_stocks = MagicMock()
        mock_db.sector_stocks.find.return_value = []

        mock_kline.distinct.return_value = ["000001"]

        closes = [11.0]*6 + [10.5]*5 + [10.0]*5 + [10.2, 10.4, 10.6, 10.9, 11.2]
        mock_kline.find.return_value.sort.return_value = [
            make_kline("000001", f"2026-07-{i+1:02d}", c)
            for i, c in enumerate(closes)
        ]

        with patch("services.selection_service.get_db", return_value=mock_db):
            result = StockSelectionService.dual_moving_average_selection(
                short_period=5, long_period=20,
                start_date="2026-07-01", end_date="2026-07-28"
            )

        assert len(result["selected_stocks"]) == 1
        assert result["selected_stocks"][0]["code"] == "000001"
        assert result["strategy"] == "dual_moving_average"

    def test_no_cross_when_price_declining(self):
        mock_db = MagicMock()
        mock_kline = MagicMock()
        mock_selection = MagicMock()
        mock_db.stock_kline = mock_kline
        mock_db.stock_selections = mock_selection
        mock_db.sector_stocks = MagicMock()
        mock_db.sector_stocks.find.return_value = []

        mock_kline.distinct.return_value = ["000001"]
        closes = [10.0]*10 + [9.5]*5 + [9.0]*5 + [8.5, 8.3, 8.0, 7.8, 7.5]
        mock_kline.find.return_value.sort.return_value = [
            make_kline("000001", f"2026-07-{i+1:02d}", c)
            for i, c in enumerate(closes)
        ]

        with patch("services.selection_service.get_db", return_value=mock_db):
            result = StockSelectionService.dual_moving_average_selection(
                short_period=5, long_period=20,
                start_date="2026-07-01", end_date="2026-07-28"
            )

        assert len(result["selected_stocks"]) == 0

    def test_skips_stock_with_insufficient_data(self):
        mock_db = MagicMock()
        mock_kline = MagicMock()
        mock_selection = MagicMock()
        mock_db.stock_kline = mock_kline
        mock_db.stock_selections = mock_selection
        mock_db.sector_stocks = MagicMock()
        mock_db.sector_stocks.find.return_value = []

        mock_kline.distinct.return_value = ["000001"]
        mock_kline.find.return_value.sort.return_value = [
            make_kline("000001", "2026-07-01", 10.0)
        ]

        with patch("services.selection_service.get_db", return_value=mock_db):
            result = StockSelectionService.dual_moving_average_selection(
                short_period=5, long_period=20,
                start_date="2026-07-01", end_date="2026-07-02"
            )

        assert len(result["selected_stocks"]) == 0


class TestGetSelectionResults:

    def test_returns_paginated_results(self):
        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_db.stock_selections = mock_coll
        mock_db.sector_stocks = MagicMock()
        mock_db.sector_stocks.find.return_value = []

        mock_coll.count_documents.return_value = 1
        mock_coll.find.return_value.sort.return_value.skip.return_value.limit.return_value = [
            {
                "code": "000001", "name": "平安银行",
                "short_ma": 11.0, "long_ma": 10.5,
                "current_price": 11.2, "change_pct": 5.0,
                "selection_date": datetime(2026, 7, 24, 10, 30),
                "strategy": "dual_moving_average",
                "params": {"short_period": 5, "long_period": 20}
            }
        ]

        with patch("services.selection_service.get_db", return_value=mock_db):
            result = StockSelectionService.get_selection_results(page=1, page_size=20)

        assert result["total"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["code"] == "000001"
        assert result["page"] == 1
        assert result["page_size"] == 20
