import pytest
import requests


class TestKlineEndpointE2E:

    def test_kline_endpoint_returns_404_for_unknown_stock(self, api_url: str, auth_header: dict):
        resp = requests.get(f"{api_url}/sectors/kline/NONEXIST",
                            headers=auth_header, timeout=10)
        assert resp.status_code == 404

    def test_kline_endpoint_supports_date_range(self, api_url: str, auth_header: dict):
        resp = requests.get(
            f"{api_url}/sectors/kline/000001?start_date=2026-01-01&end_date=2026-06-30",
            headers=auth_header, timeout=10,
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "data" in data


class TestIndicatorComputationE2E:

    def test_compute_with_real_stock_data(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from bin.indicator_calculator import compute_stock_indicators

        klines = []
        base = 15.0
        for i in range(30):
            klines.append({
                "date": f"202607{1+i:02d} 15:00",
                "open": base,
                "close": base + 0.3,
                "high": base + 0.5,
                "low": base - 0.2,
                "volume": 2000000,
            })
            base += 0.5

        result = compute_stock_indicators(klines)
        assert result is not None
        for date_str, vals in result.items():
            for key in ("ma5", "ma10", "ma20", "rsi", "atr", "adx", "amplitude"):
                assert key in vals, f"Missing {key} for {date_str}"
                assert vals[key] is not None

    def test_rsi_direction_changes_with_trend(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from bin.indicator_calculator import compute_stock_indicators

        klines = []
        close = 50.0
        for i in range(40):
            if i < 20:
                close = round(close + 0.5, 2)
            else:
                close = round(close - 1.0, 2)
            klines.append({
                "date": f"202607{1+i:02d} 15:00",
                "open": close - 0.1,
                "close": close,
                "high": close + 0.3,
                "low": close - 0.3,
                "volume": 1000000,
            })

        result = compute_stock_indicators(klines)
        assert result is not None
        values = list(result.values())
        last_rsi = values[-1]["rsi"]
        assert last_rsi < 50, f"RSI should be <50 after drop, got {last_rsi}"
