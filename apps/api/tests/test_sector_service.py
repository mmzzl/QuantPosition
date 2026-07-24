import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock
from services.sector_service import SectorService


def make_kline(code, date, close, open_p=None, high=None, low=None, volume=100000, amount=None):
    o = open_p if open_p is not None else close * 0.99
    h = high if high is not None else close * 1.02
    lv = low if low is not None else close * 0.98
    a = amount if amount is not None else volume * close
    return {"code": code, "date": date, "open": o, "close": close,
            "high": h, "low": lv, "volume": volume, "amount": a, "frequency": 9}


def make_agg_result(*codes_with_first_last):
    """Make aggregate pipeline result: [{_id, first_close, last_date, last_close, last_volume}]"""
    return [{"_id": c, "first_close": f, "last_close": l, "last_volume": v}
            for c, f, l, v in codes_with_first_last]


def make_db(collection_mocks=None):
    """Create a mock_db where __getitem__ (db['name']) returns the same mock as attribute (db.name)"""
    mock_db = MagicMock()
    collection_mocks = collection_mocks or {}
    def getitem(key):
        if key not in collection_mocks:
            collection_mocks[key] = MagicMock()
        return collection_mocks[key]
    mock_db.__getitem__.side_effect = getitem
    for name, col_mock in collection_mocks.items():
        setattr(mock_db, name, col_mock)
    return mock_db


def mock_heatmap_db(sector_list, sector_stocks_list, agg_result):
    ss = MagicMock()
    ss.find.side_effect = [sector_list, sector_stocks_list]
    sk = MagicMock()
    sk.aggregate.return_value = agg_result
    mock_db = make_db({"sector_stocks": ss, "stock_kline": sk})
    return mock_db


class TestGetSectorHeatmap:

    def test_returns_correct_structure(self):
        sectors = [
            {"sector_name": "银行", "sector_code": "BK001"},
            {"sector_name": "医药", "sector_code": "BK002"},
        ]
        stocks = [
            {"sector_name": "银行", "stock_code": "000001", "stock_name": "平安银行"},
            {"sector_name": "银行", "stock_code": "000002", "stock_name": "招商银行"},
            {"sector_name": "医药", "stock_code": "600001", "stock_name": "恒瑞医药"},
        ]
        agg = make_agg_result(
            ("000001", 10.0, 11.0, 500000),
            ("000002", 20.0, 22.0, 300000),
            ("600001", 30.0, 27.0, 200000),
        )
        mock_db = mock_heatmap_db(sectors, stocks, agg)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h", start_date="2026-07-01", end_date="2026-07-02")
        assert "sectors" in result
        assert "period" in result
        assert "total_sectors" in result
        assert "start_date" in result
        assert "end_date" in result
        assert result["period"] == "24h"
        assert result["total_sectors"] == 2
        assert result["start_date"] == "2026-07-01"
        assert result["end_date"] == "2026-07-02"

    def test_calculates_change_pct_correctly(self):
        sectors = [{"sector_name": "银行", "sector_code": "BK001"}]
        stocks = [{"sector_name": "银行", "stock_code": "000001", "stock_name": "平安银行"}]
        agg = make_agg_result(("000001", 10.0, 11.0, 500000))
        mock_db = mock_heatmap_db(sectors, stocks, agg)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h", start_date="2026-07-01", end_date="2026-07-02")
        assert len(result["sectors"]) == 1
        assert result["sectors"][0]["sector_name"] == "银行"
        assert result["sectors"][0]["change_pct"] == 10.0

    def test_multiple_stocks_average_change(self):
        sectors = [{"sector_name": "银行", "sector_code": "BK001"}]
        stocks = [
            {"sector_name": "银行", "stock_code": "000001", "stock_name": "平安银行"},
            {"sector_name": "银行", "stock_code": "000002", "stock_name": "招商银行"},
        ]
        agg = make_agg_result(
            ("000001", 10.0, 11.0, 500000),
            ("000002", 20.0, 22.0, 300000),
        )
        mock_db = mock_heatmap_db(sectors, stocks, agg)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h", start_date="2026-07-01", end_date="2026-07-02")
        assert len(result["sectors"]) == 1
        assert result["sectors"][0]["change_pct"] == 10.0
        assert result["sectors"][0]["stock_count"] == 2

    def test_handles_24h_period(self):
        ss = MagicMock()
        ss.find.side_effect = [[{"sector_name": "银行", "sector_code": "BK001"}], []]
        mock_db = make_db({"sector_stocks": ss, "stock_kline": MagicMock()})
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h")
        assert result["period"] == "24h"

    def test_handles_7d_period(self):
        ss = MagicMock()
        ss.find.side_effect = [[{"sector_name": "银行", "sector_code": "BK001"}], []]
        mock_db = make_db({"sector_stocks": ss, "stock_kline": MagicMock()})
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="7d")
        assert result["period"] == "7d"

    def test_handles_30d_period(self):
        ss = MagicMock()
        ss.find.side_effect = [[{"sector_name": "银行", "sector_code": "BK001"}], []]
        mock_db = make_db({"sector_stocks": ss, "stock_kline": MagicMock()})
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="30d")
        assert result["period"] == "30d"

    def test_handles_custom_date_range(self):
        sectors = [{"sector_name": "银行", "sector_code": "BK001"}]
        stocks = [{"sector_name": "银行", "stock_code": "000001", "stock_name": "平安银行"}]
        agg = make_agg_result(("000001", 9.0, 10.0, 500000))
        mock_db = mock_heatmap_db(sectors, stocks, agg)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="30d", start_date="2026-06-01", end_date="2026-06-15")
        assert result["start_date"] == "2026-06-01"
        assert result["end_date"] == "2026-06-15"

    def test_handles_empty_kline_data(self):
        sectors = [{"sector_name": "银行", "sector_code": "BK001"}]
        stocks = [{"sector_name": "银行", "stock_code": "000001", "stock_name": "平安银行"}]
        mock_db = mock_heatmap_db(sectors, stocks, [])
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h", start_date="2026-07-01", end_date="2026-07-02")
        assert len(result["sectors"]) == 1
        assert result["sectors"][0]["change_pct"] == 0
        assert result["sectors"][0]["volume"] == 0

    def test_sectors_sorted_by_change_pct_descending(self):
        sectors = [
            {"sector_name": "医药", "sector_code": "BK002"},
            {"sector_name": "银行", "sector_code": "BK001"},
        ]
        stocks = [
            {"sector_name": "医药", "stock_code": "600001", "stock_name": "恒瑞"},
            {"sector_name": "银行", "stock_code": "000001", "stock_name": "平安银行"},
        ]
        agg = make_agg_result(
            ("600001", 30.0, 27.0, 200000),
            ("000001", 10.0, 11.0, 500000),
        )
        mock_db = mock_heatmap_db(sectors, stocks, agg)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h", start_date="2026-07-01", end_date="2026-07-02")
        assert result["sectors"][0]["change_pct"] > result["sectors"][1]["change_pct"]
        assert result["sectors"][0]["sector_name"] == "银行"

    def test_stock_code_with_exchange_suffix(self):
        sectors = [{"sector_name": "银行", "sector_code": "BK001"}]
        stocks = [{"sector_name": "银行", "stock_code": "000001.SZ", "stock_name": "平安银行"}]
        agg = make_agg_result(("000001", 10.0, 11.0, 500000))
        mock_db = mock_heatmap_db(sectors, stocks, agg)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_heatmap(period="24h", start_date="2026-07-01", end_date="2026-07-02")
        assert len(result["sectors"]) == 1
        assert result["sectors"][0]["change_pct"] == 10.0


class TestGetSectorStocks:

    @staticmethod
    def _make_mock_db(stocks_in_sector, kline_data=None):
        ss = MagicMock()
        ss.find.return_value = stocks_in_sector
        sort_mock = MagicMock()
        sort_mock.sort.return_value = kline_data or []
        sk = MagicMock()
        sk.find.return_value = sort_mock
        mock_db = make_db({"sector_stocks": ss, "stock_kline": sk})
        return mock_db

    def test_returns_correct_structure(self):
        stocks = [{"sector_name": "银行", "sector_code": "BK001", "stock_code": "000001", "stock_name": "平安银行"}]
        kline_data = [make_kline("000001", d, c) for d, c in [("2026-07-01", 10.0), ("2026-07-02", 11.0)]]
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_stocks("银行", start_date="2026-07-01", end_date="2026-07-02")
        assert "sector_name" in result
        assert "sector_code" in result
        assert "stocks" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert result["sector_name"] == "银行"
        assert result["sector_code"] == "BK001"
        assert len(result["stocks"]) == 1
        assert result["total"] == 1

    def test_nonexistent_sector_returns_empty(self):
        mock_db = self._make_mock_db([])
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_stocks("不存在板块")
        assert len(result["stocks"]) == 0
        assert result["total"] == 0

    def test_calculates_per_stock_change_pct(self):
        stocks = [{"sector_name": "银行", "sector_code": "BK001", "stock_code": "000001", "stock_name": "平安银行"}]
        kline_data = [make_kline("000001", d, c) for d, c in [("2026-07-01", 10.0), ("2026-07-02", 11.0)]]
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_stocks("银行", start_date="2026-07-01", end_date="2026-07-02")
        assert result["stocks"][0]["change_pct"] == 10.0
        assert result["stocks"][0]["current_price"] == 11.0
        assert result["stocks"][0]["first_price"] == 10.0

    def test_supports_sorting_by_change_pct(self):
        stocks = [
            {"sector_name": "银行", "sector_code": "BK001", "stock_code": "000001", "stock_name": "平安银行"},
            {"sector_name": "银行", "sector_code": "BK001", "stock_code": "000002", "stock_name": "招商银行"},
        ]
        kline_data = [
            make_kline("000001", "2026-07-01", close=10.0),
            make_kline("000001", "2026-07-02", close=11.0),
            make_kline("000002", "2026-07-01", close=20.0),
            make_kline("000002", "2026-07-02", close=21.0),
        ]
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            desc = SectorService.get_sector_stocks("银行", sort_by="change_pct", sort_order="desc",
                                                    start_date="2026-07-01", end_date="2026-07-02")
            asc = SectorService.get_sector_stocks("银行", sort_by="change_pct", sort_order="asc",
                                                   start_date="2026-07-01", end_date="2026-07-02")
        assert desc["stocks"][0]["change_pct"] >= desc["stocks"][-1]["change_pct"]
        assert asc["stocks"][0]["change_pct"] <= asc["stocks"][-1]["change_pct"]

    def test_supports_sorting_by_volume(self):
        stocks = [
            {"sector_name": "银行", "sector_code": "BK001", "stock_code": "000001", "stock_name": "平安银行"},
            {"sector_name": "银行", "sector_code": "BK001", "stock_code": "000002", "stock_name": "招商银行"},
        ]
        kline_data = [
            make_kline("000001", "2026-07-02", close=11.0, volume=50000),
            make_kline("000002", "2026-07-02", close=21.0, volume=100000),
            make_kline("000001", "2026-07-01", close=10.0, volume=30000),
            make_kline("000002", "2026-07-01", close=20.0, volume=80000),
        ]
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_stocks("银行", sort_by="volume", sort_order="desc",
                                                      start_date="2026-07-01", end_date="2026-07-02")
        assert result["stocks"][0]["volume"] >= result["stocks"][-1]["volume"]

    def test_supports_sorting_by_name(self):
        stocks = [
            {"sector_name": "银行", "sector_code": "BK001", "stock_code": "000001", "stock_name": "AAA"},
            {"sector_name": "银行", "sector_code": "BK001", "stock_code": "000002", "stock_name": "BBB"},
        ]
        kline_data = [
            make_kline("000001", "2026-07-01", close=10.0),
            make_kline("000001", "2026-07-02", close=11.0),
            make_kline("000002", "2026-07-01", close=20.0),
            make_kline("000002", "2026-07-02", close=22.0),
        ]
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            asc = SectorService.get_sector_stocks("银行", sort_by="name", sort_order="asc",
                                                   start_date="2026-07-01", end_date="2026-07-02")
            desc = SectorService.get_sector_stocks("银行", sort_by="name", sort_order="desc",
                                                    start_date="2026-07-01", end_date="2026-07-02")
        assert asc["stocks"][0]["name"] < asc["stocks"][-1]["name"]
        assert desc["stocks"][0]["name"] > desc["stocks"][-1]["name"]

    def test_supports_pagination(self):
        stocks = [{"sector_name": "银行", "sector_code": "BK001", "stock_code": f"000{i:03d}", "stock_name": f"Stock{i}"}
                  for i in range(1, 11)]
        kline_data = []
        for i in range(1, 11):
            kline_data.append(make_kline(f"000{i:03d}", "2026-07-01", close=10.0))
            kline_data.append(make_kline(f"000{i:03d}", "2026-07-02", close=11.0))
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            p1 = SectorService.get_sector_stocks("银行", page=1, page_size=3,
                                                   start_date="2026-07-01", end_date="2026-07-02")
            p2 = SectorService.get_sector_stocks("银行", page=2, page_size=3,
                                                   start_date="2026-07-01", end_date="2026-07-02")
        assert len(p1["stocks"]) == 3
        assert len(p2["stocks"]) == 3
        assert p1["page"] == 1
        assert p2["page"] == 2
        assert p1["stocks"][0]["code"] != p2["stocks"][0]["code"]
        assert p1["total"] == 10

    def test_stock_code_with_exchange_suffix(self):
        stocks = [{"sector_name": "银行", "sector_code": "BK001", "stock_code": "000001.SZ", "stock_name": "平安银行"}]
        kline_data = [make_kline("000001", d, c) for d, c in [("2026-07-01", 10.0), ("2026-07-02", 11.0)]]
        mock_db = self._make_mock_db(stocks, kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_sector_stocks("银行", start_date="2026-07-01", end_date="2026-07-02")
        assert result["stocks"][0]["code"] == "000001.SZ"


class TestGetKlineData:

    @staticmethod
    def _make_mock_db(sector_stock=None, kline_data=None, latest_kline=None):
        ss = MagicMock()
        ss.find_one.return_value = sector_stock
        sort_mock = MagicMock()
        sort_mock.sort.return_value = kline_data or []
        sk = MagicMock()
        sk.find.return_value = sort_mock
        sk.find_one.return_value = latest_kline
        mock_db = make_db({"sector_stocks": ss, "stock_kline": sk})
        return mock_db

    def test_returns_correct_structure(self):
        sector_stock = {"stock_code": "000001", "stock_name": "平安银行"}
        kline_data = [make_kline("000001", d, c) for d, c in [("2026-07-01", 10.0), ("2026-07-02", 11.0)]]
        mock_db = self._make_mock_db(sector_stock=sector_stock, kline_data=kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_kline_data("000001", start_date="2026-07-01", end_date="2026-07-02")
        assert "code" in result
        assert "name" in result
        assert "period" in result
        assert "data" in result
        assert "total" in result
        assert result["code"] == "000001"
        assert result["name"] == "平安银行"
        assert result["period"] == "daily"
        assert result["total"] == 2

    def test_missing_kline_returns_empty_data(self):
        sector_stock = {"stock_code": "000001", "stock_name": "平安银行"}
        mock_db = self._make_mock_db(sector_stock=sector_stock, kline_data=[])
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_kline_data("000001", start_date="2026-07-01", end_date="2026-07-02")
        assert result["total"] == 0
        assert len(result["data"]) == 0

    def test_missing_sector_stock_and_kline_returns_empty(self):
        mock_db = self._make_mock_db(sector_stock=None, kline_data=[], latest_kline=None)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_kline_data("000001")
        assert result["total"] == 0
        assert result["name"] == ""

    def test_strips_exchange_suffix(self):
        sector_stock = {"stock_code": "000001", "stock_name": "平安银行"}
        kline_data = [make_kline("000001", "2026-07-01", close=10.0)]
        mock_db = self._make_mock_db(sector_stock=sector_stock, kline_data=kline_data)
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_kline_data("000001.SZ", start_date="2026-07-01", end_date="2026-07-02")
        assert result["code"] == "000001.SZ"
        assert result["name"] == "平安银行"

    def test_handles_auto_date_range(self):
        sector_stock = {"stock_code": "000001", "stock_name": "平安银行"}
        latest_kline = make_kline("000001", "2026-07-02", close=11.0)
        kline_data = [make_kline("000001", "2025-07-03", close=9.0), make_kline("000001", "2026-07-02", close=11.0)]
        ss = MagicMock()
        ss.find_one.return_value = sector_stock
        sort_mock = MagicMock()
        sort_mock.sort.return_value = kline_data
        sk = MagicMock()
        sk.find_one.return_value = latest_kline
        sk.find.return_value = sort_mock
        mock_db = make_db({"sector_stocks": ss, "stock_kline": sk})
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_kline_data("000001")
        assert len(result["data"]) == 2
        assert result["total"] == 2

    def test_auto_date_range_no_latest_kline(self):
        sector_stock = {"stock_code": "000001", "stock_name": "平安银行"}
        kline_data = [make_kline("000001", "2025-01-01", close=9.0)]
        ss = MagicMock()
        ss.find_one.return_value = sector_stock
        sort_mock = MagicMock()
        sort_mock.sort.return_value = kline_data
        sk = MagicMock()
        sk.find_one.return_value = None
        sk.find.return_value = sort_mock
        mock_db = make_db({"sector_stocks": ss, "stock_kline": sk})
        with patch("services.sector_service.get_db", return_value=mock_db):
            result = SectorService.get_kline_data("000001")
        assert result["total"] == 1
