import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from datetime import datetime
from services.paper_trade_service import PaperTradingService


def make_news_selection(code="000001", name="平安银行", expected_return=15.0, current_price=12.5):
    return {
        "code": code,
        "name": name,
        "expected_return": expected_return,
        "current_price": current_price,
        "created_at": datetime.now(),
    }


def make_dual_ma_selection(code="000001", name="平安银行", change_pct=5.0, current_price=12.5):
    return {
        "code": code,
        "name": name,
        "change_pct": change_pct,
        "current_price": current_price,
        "selection_date": datetime.now(),
    }


def _configure_db(holdings_find_one=None, holdings_list=None, trades_list=None):
    mock_db = MagicMock()

    cache_coll = MagicMock()
    selection_coll = MagicMock()
    holdings_coll = MagicMock()
    trades_coll = MagicMock()

    # Route subscript access (db["paper_holdings"]) to the same objects
    def getitem(key):
        mapping = {
            "paper_holdings": holdings_coll,
            "paper_trades": trades_coll,
        }
        return mapping.get(key, MagicMock())

    mock_db.__getitem__.side_effect = getitem

    # Attribute access for db.news_selection_cache / db.stock_selections
    mock_db.news_selection_cache = cache_coll
    mock_db.stock_selections = selection_coll

    # For other subscript access (db["paper_holdings"]), we want holdings_coll
    # But paper_holdings is already in the __getitem__ mapping

    holdings_coll.find_one.return_value = holdings_find_one

    if holdings_list is not None:
        holdings_coll.find.return_value.sort.return_value = holdings_list

    if trades_list is not None:
        trades_coll.find.return_value.sort.return_value.limit.return_value = trades_list

    return mock_db, cache_coll, selection_coll, holdings_coll, trades_coll


class TestSyncBuy:

    def test_sync_buy_returns_synced_count(self):
        mock_db, cache_coll, selection_coll, holdings_coll, trades_coll = _configure_db(
            holdings_find_one=None
        )
        cache_coll.find.return_value.sort.return_value.limit.return_value = [
            make_news_selection(),
        ]
        selection_coll.find.return_value.sort.return_value.limit.return_value = [
            make_dual_ma_selection("000002", "万科A"),
        ]

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            with patch("services.paper_trade_service.get_stock_price", return_value=13.0):
                result = PaperTradingService.sync_buy()

        assert result == {"synced_count": 2}
        assert holdings_coll.insert_one.call_count == 2
        assert trades_coll.insert_one.call_count == 2

    def test_sync_buy_empty_selections_returns_zero(self):
        mock_db, cache_coll, selection_coll, holdings_coll, trades_coll = _configure_db()
        cache_coll.find.return_value.sort.return_value.limit.return_value = []
        selection_coll.find.return_value.sort.return_value.limit.return_value = []

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            result = PaperTradingService.sync_buy()

        assert result == {"synced_count": 0}

    def test_sync_buy_skips_missing_price(self):
        mock_db, cache_coll, selection_coll, holdings_coll, trades_coll = _configure_db()
        cache_coll.find.return_value.sort.return_value.limit.return_value = [
            make_news_selection(),
        ]
        selection_coll.find.return_value.sort.return_value.limit.return_value = []

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            with patch("services.paper_trade_service.get_stock_price", return_value=None):
                result = PaperTradingService.sync_buy()

        assert result == {"synced_count": 0}

    def test_sync_buy_merges_existing_holding(self):
        existing = {"_id": "existing_id", "code": "000001", "quantity": 100, "avg_cost": 10.0}
        mock_db, cache_coll, selection_coll, holdings_coll, trades_coll = _configure_db(
            holdings_find_one=existing
        )
        cache_coll.find.return_value.sort.return_value.limit.return_value = [
            make_news_selection(),
        ]
        selection_coll.find.return_value.sort.return_value.limit.return_value = []

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            with patch("services.paper_trade_service.get_stock_price", return_value=13.0):
                result = PaperTradingService.sync_buy()

        assert result == {"synced_count": 1}
        holdings_coll.update_one.assert_called_once()
        call_args = holdings_coll.update_one.call_args[0][1]
        assert call_args["$set"]["quantity"] == 200


class TestSyncSell:

    def test_sync_sell_no_rules_returns_none(self):
        mock_db = MagicMock()
        mock_db.trading_rules = MagicMock()
        mock_db.trading_rules.find.return_value.sort.return_value = []

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            result = PaperTradingService.sync_sell()

        assert result is None

    def test_sync_sell_engine_import_fail_logs_only(self):
        result = PaperTradingService.sync_sell()
        assert result is None


class TestGetPositions:

    def test_get_positions_returns_empty(self):
        mock_db, _, _, holdings_coll, trades_coll = _configure_db()
        holdings_coll.find.return_value.sort.return_value = []
        trades_coll.find.return_value.sort.return_value.limit.return_value = []

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            result = PaperTradingService.get_positions()

        assert result["open"]["count"] == 0
        assert result["open"]["positions"] == []
        assert result["closed"]["count"] == 0

    def test_get_positions_with_holdings(self):
        mock_db, _, _, holdings_coll, trades_coll = _configure_db(
            holdings_list=[
                {
                    "code": "000001",
                    "name": "平安银行",
                    "quantity": 100,
                    "avg_cost": 12.0,
                    "strategy": "news",
                    "created_at": datetime.now(),
                }
            ],
            trades_list=[]
        )

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            with patch("services.paper_trade_service.get_stock_price", return_value=13.5):
                result = PaperTradingService.get_positions()

        assert result["open"]["count"] == 1
        pos = result["open"]["positions"][0]
        assert pos["code"] == "000001"
        assert pos["quantity"] == 100
        assert pos["avg_cost"] == 12.0
        assert pos["current_price"] == 13.5
        assert pos["unrealized_pnl"] == 150.0


class TestClear:

    def test_clear_deletes_all(self):
        mock_db, _, _, holdings_coll, trades_coll = _configure_db()

        with patch("services.paper_trade_service.get_db", return_value=mock_db):
            result = PaperTradingService.clear()

        assert result is None
        holdings_coll.delete_many.assert_called_once_with({})
        trades_coll.delete_many.assert_called_once_with({})
