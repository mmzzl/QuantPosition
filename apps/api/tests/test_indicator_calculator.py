import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bin.indicator_calculator import compute_stock_indicators, IndicatorCalculator


def make_kline(date, open_p, close, high, low, volume=100000):
    return {"date": date, "open": open_p, "close": close,
            "high": high, "low": low, "volume": volume}


def test_compute_all_keys():
    klines = []
    base = 10.0
    for i in range(20):
        klines.append(make_kline(
            f"202607{1+i:02d} 15:00", base, base + 0.1, base + 0.3, base - 0.2,
        ))
        base += 0.5

    result = compute_stock_indicators(klines)
    assert result is not None
    for date_str, vals in result.items():
        for key in ("ma5", "ma10", "ma20", "rsi", "atr", "adx", "amplitude"):
            assert key in vals, f"missing {key} for {date_str}"


def test_ma5_equals_close_constant_price():
    klines = []
    for i in range(20):
        klines.append(make_kline(
            f"202607{1+i:02d} 15:00", 10.0, 10.0, 10.5, 9.5,
        ))

    result = compute_stock_indicators(klines)
    assert result is not None
    date_strs = list(result.keys())
    entry = result[date_strs[4]]
    assert entry["ma5"] == 10.0


def test_empty_klines():
    result = compute_stock_indicators([])
    assert result is None


def test_insufficient_klines():
    klines = []
    for i in range(19):
        klines.append(make_kline(
            f"202607{1+i:02d} 15:00", 10.0, 10.0, 10.5, 9.5,
        ))
    result = compute_stock_indicators(klines)
    assert result is None


def test_rsi_above_50_when_upward():
    klines = []
    close = 10.0
    for i in range(30):
        open_p = close
        close = round(close + 0.3, 2)
        high = round(close + 0.2, 2)
        low = round(open_p - 0.1, 2)
        klines.append(make_kline(
            f"202607{1+i:02d} 15:00", open_p, close, high, low,
        ))

    result = compute_stock_indicators(klines)
    assert result is not None
    last_rsi = list(result.values())[-1]["rsi"]
    assert last_rsi > 50


from unittest.mock import patch, MagicMock
from datetime import datetime


class TestRunDailyUpdate:

    def test_skip_when_no_codes_with_klines_today(self):
        from bin.indicator_calculator import run_daily_update
        mock_db = MagicMock()
        with patch("bin.indicator_calculator.get_db", return_value=mock_db):
            with patch("bin.indicator_calculator.get_codes_with_klines_today", return_value=[]):
                with patch("bin.indicator_calculator.update_stock_indicators") as mock_update:
                    run_daily_update()
        mock_update.assert_not_called()

    def test_updates_indicators_for_stocks_with_today_klines(self):
        from bin.indicator_calculator import run_daily_update
        mock_db = MagicMock()
        with patch("bin.indicator_calculator.get_db", return_value=mock_db):
            with patch("bin.indicator_calculator.get_codes_with_klines_today", return_value=["000001"]):
                with patch("bin.indicator_calculator.update_stock_indicators", return_value=(1, 0)):
                    run_daily_update()


class TestBackfillIndicators:

    def test_backfill_all_indicators_processes_all_stocks(self):
        from bin.indicator_calculator import backfill_all_indicators
        mock_db = MagicMock()
        all_codes = [f"{i:06d}" for i in range(3)]
        mock_db.stock_kline.distinct.return_value = all_codes

        def make_kline(date, close_val):
            return {"date": date, "open": close_val, "close": close_val,
                    "high": close_val + 0.2, "low": close_val - 0.2, "volume": 100000}

        mock_db.stock_kline.find.return_value.sort.return_value = [
            make_kline(f"202607{d:02d}", 10.0) for d in range(1, 61)
        ]
        with patch("bin.indicator_calculator.update_stock_indicators", return_value=(3, 0)):
            result = backfill_all_indicators(mock_db, chunk_size=200)
        assert result == (3, 0)

    def test_backfill_skips_error_stocks(self):
        from bin.indicator_calculator import backfill_all_indicators
        mock_db = MagicMock()
        mock_db.stock_kline.distinct.return_value = ["000001", "000002"]

        def make_kline(date, close_val):
            return {"date": date, "open": close_val, "close": close_val,
                    "high": close_val + 0.2, "low": close_val - 0.2, "volume": 100000}

        mock_db.stock_kline.find.return_value.sort.return_value = [
            make_kline(f"202607{d:02d}", 10.0) for d in range(1, 61)
        ]
        with patch("bin.indicator_calculator.update_stock_indicators", return_value=(1, 1)):
            result = backfill_all_indicators(mock_db, chunk_size=200)
        assert result == (1, 1)


class TestIndicatorCalculatorClass:
    def test_calculate_returns_dict_for_valid_klines(self):
        calculator = IndicatorCalculator()
        klines = []
        base = 10.0
        for i in range(20):
            klines.append(make_kline(
                f"202607{1+i:02d} 15:00", base, base + 0.1, base + 0.3, base - 0.2,
            ))
            base += 0.5
        result = calculator.calculate("000001", klines)
        assert result is not None
        assert isinstance(result, dict)
        last_key = list(result.keys())[-1]
        assert "ma5" in result[last_key]
        assert "rsi" in result[last_key]
        assert "atr" in result[last_key]
        assert "adx" in result[last_key]

    def test_calculate_returns_none_for_insufficient_data(self):
        calculator = IndicatorCalculator()
        klines = [make_kline(f"202607{i:02d} 15:00", 10.0, 10.0, 10.5, 9.5)
                  for i in range(1, 5)]
        result = calculator.calculate("000001", klines)
        assert result is None

    def test_backfill_returns_tuple(self):
        mock_db = MagicMock()
        mock_db.stock_kline.distinct.return_value = ["000001", "000002"]
        mock_kline = make_kline("20260701 15:00", 10.0, 10.0, 10.5, 9.5)
        mock_db.stock_kline.find.return_value.sort.return_value = [mock_kline] * 60
        with patch("bin.indicator_calculator.update_stock_indicators", return_value=(2, 0)):
            calculator = IndicatorCalculator(db=mock_db)
            result = calculator.backfill(chunk_size=200)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] >= 0

    def test_init_uses_given_db(self):
        mock_db = MagicMock()
        calculator = IndicatorCalculator(db=mock_db)
        assert calculator.db is mock_db
