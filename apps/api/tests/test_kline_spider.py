import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from datetime import datetime

from bin.kline_spider import _tencent_kline, StockKlineScraper, _multi_source_kline
import requests


def test_tencent_kline_valid_response():
    mock_r = MagicMock()
    mock_r.json.return_value = {
        "data": {
            "sh000001": {
                "qfqday": [
                    ["20260722", "10.5", "10.6", "10.8", "10.3", "1000000"],
                    ["20260723", "10.6", "10.7", "10.9", "10.4", "1100000"],
                ]
            }
        }
    }
    with patch("bin.kline_spider.requests.get", return_value=mock_r):
        result = _tencent_kline("000001")

    assert result is not None
    assert len(result) == 2
    for r in result:
        assert r["code"] == "000001"
        assert r["frequency"] == 9
        assert r["date"].endswith(" 15:00")
    assert result[0]["date"].startswith("20260722")
    assert result[0]["open"] == 10.5
    assert result[0]["close"] == 10.6
    assert result[0]["high"] == 10.8
    assert result[0]["low"] == 10.3
    assert result[0]["volume"] == 1000000
    assert result[1]["open"] == 10.6
    assert result[1]["close"] == 10.7


def test_tencent_kline_http_error():
    with patch("bin.kline_spider.requests.get", side_effect=Exception("HTTP error")):
        result = _tencent_kline("000001")
    assert result is None


def test_tencent_kline_empty_response():
    mock_r = MagicMock()
    mock_r.json.return_value = {"data": {}}
    with patch("bin.kline_spider.requests.get", return_value=mock_r):
        result = _tencent_kline("000001")
    assert result == []


def test_save_klines_with_records():
    scraper = StockKlineScraper()
    scraper.storage = MagicMock()

    records = [
        {
            "code": "000001", "date": "20260722 15:00", "frequency": 9,
            "open": 10.5, "close": 10.6, "high": 10.8, "low": 10.3,
            "volume": 1000000, "amount": 0.0, "adjust": "qfq",
            "crawl_time": datetime.now().isoformat(),
        }
    ]
    scraper.save_klines(records)

    scraper.storage.bulk_write.assert_called_once()
    args, kwargs = scraper.storage.bulk_write.call_args
    operations = args[0]
    assert len(operations) == 1
    from pymongo import UpdateOne
    assert isinstance(operations[0], UpdateOne)
    assert operations[0]._filter == {"code": "000001", "date": "20260722 15:00", "frequency": 9}


class TestStockKlineScraper:

    def test_fetch_kline_incremental_filters_by_latest(self):
        scraper = StockKlineScraper()
        scraper.storage = MagicMock()
        with patch.object(scraper, "_get_latest_bar_time", return_value="20260722 15:00"):
            with patch.object(scraper, "_fetch_kline") as mock_fetch:
                mock_fetch.side_effect = lambda code: (
                    [{"date": "20260722 15:00", "code": code},
                     {"date": "20260723 15:00", "code": code}]
                    if code == "000001" else []
                )
                with patch.object(scraper, "_get_all_stock_codes", return_value=["000001"]):
                    result = scraper.fetch_daily_klines()
        assert result["success"] == 1

    def test_concurrent_fetch_accumulates_pending(self):
        scraper = StockKlineScraper()
        scraper.storage = MagicMock()
        with patch.object(scraper, "_get_all_stock_codes", return_value=[f"{i:06d}" for i in range(5)]):
            with patch.object(scraper, "_fetch_kline", return_value=[{"code": "000001", "date": "20260723 15:00"}]):
                with patch.object(scraper, "save_klines") as mock_save:
                    scraper.fetch_daily_klines()
        assert mock_save.call_count >= 1

    def test_save_klines_bulk_write_on_threshold(self):
        scraper = StockKlineScraper()
        scraper.storage = MagicMock()
        records = [
            {"code": f"{i:06d}", "date": "20260723 15:00", "frequency": 9,
             "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9,
             "volume": 100000, "amount": 0.0, "adjust": "qfq",
             "crawl_time": datetime.now().isoformat()}
            for i in range(2000)
        ]
        scraper.save_klines(records)
        scraper.storage.bulk_write.assert_called_once()


class TestMultiSourceKline:
    def test_tencent_fallback_to_sina(self):
        with patch("bin.kline_spider._tencent_kline", return_value=None):
            with patch("bin.kline_spider._sina_kline") as mock_sina:
                mock_sina.return_value = [{
                    "code": "000001", "date": "20260722 15:00", "frequency": 9,
                    "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9,
                    "volume": 100000, "amount": 0.0, "adjust": "qfq",
                    "source": "sina", "crawl_time": datetime.now().isoformat(),
                }]
                result = _multi_source_kline("000001")
        assert result is not None
        assert len(result) == 1
        assert result[0]["source"] == "sina"
        mock_sina.assert_called_once()

    def test_multi_source_returns_tencent_when_available(self):
        mock_data = [{
            "code": "000001", "date": "20260722 15:00", "frequency": 9,
            "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9,
            "volume": 100000, "amount": 0.0, "adjust": "qfq",
            "source": "tencent", "crawl_time": datetime.now().isoformat(),
        }]
        with patch("bin.kline_spider._tencent_kline", return_value=mock_data):
            with patch("bin.kline_spider._sina_kline") as mock_sina:
                result = _multi_source_kline("000001")
        assert result is not None
        assert result[0]["source"] == "tencent"
        mock_sina.assert_not_called()


class TestFetchStockContract:
    def test_fetch_stock_returns_kline_list(self):
        scraper = StockKlineScraper()
        mock_data = [{
            "code": "000001", "date": "20260722 15:00", "frequency": 9,
            "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9,
            "volume": 100000, "amount": 0.0, "adjust": "qfq",
            "source": "tencent", "crawl_time": datetime.now().isoformat(),
        }]
        with patch("bin.kline_spider._multi_source_kline", return_value=mock_data):
            with patch.object(StockKlineScraper, "_cutoff_date", return_value="9999-12-31"):
                result = scraper.fetch_stock("000001")
        assert result is not None
        assert len(result) == 1
        assert result[0]["code"] == "000001"

    def test_fetch_stock_returns_none_on_failure(self):
        scraper = StockKlineScraper()
        with patch("bin.kline_spider._multi_source_kline", return_value=None):
            result = scraper.fetch_stock("000001")
        assert result is None


class TestBatchUpdate:
    def test_batch_update_returns_success_count(self):
        scraper = StockKlineScraper()
        scraper.storage = MagicMock()
        with patch.object(scraper, "_get_all_stock_codes", return_value=["000001", "000002"]):
            with patch.object(scraper, "_fetch_kline", return_value=[
                {"code": "000001", "date": "20260722 15:00", "frequency": 9,
                 "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9,
                 "volume": 100000, "amount": 0.0, "adjust": "qfq",
                 "source": "tencent", "crawl_time": datetime.now().isoformat()},
            ]):
                with patch.object(scraper, "save_klines") as mock_save:
                    count = scraper.batch_update()
        assert count == 2


class TestRetryLogic:
    def test_tencent_kline_retries_then_fails(self):
        with patch("bin.kline_spider.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("timeout")
            with patch("bin.kline_spider.time.sleep") as mock_sleep:
                result = _tencent_kline("000001", count=320, retries=3)
        assert result is None
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    def test_tencent_kline_retry_succeeds_on_second_attempt(self):
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = requests.HTTPError("500")
        success_resp = MagicMock()
        success_resp.json.return_value = {
            "data": {
                "sh000001": {
                    "qfqday": [["20260722", "10.5", "10.6", "10.8", "10.3", "1000000"]]
                }
            }
        }
        with patch("bin.kline_spider.requests.get", side_effect=[fail_resp, success_resp]):
            with patch("bin.kline_spider.time.sleep") as mock_sleep:
                result = _tencent_kline("000001", count=320, retries=3)
        assert result is not None
        assert len(result) == 1
        assert mock_sleep.call_count == 1
