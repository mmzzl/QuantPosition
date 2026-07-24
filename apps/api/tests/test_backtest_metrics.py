import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.backtest_engine import calculate_metrics


class TestCalculateMetrics:

    def test_empty_trades(self):
        result = calculate_metrics([100000], [], 100000)
        assert result["total_trades"] == 0
        assert result["annual_return"] == 0
        assert result["sharpe_ratio"] == 0
        assert result["max_drawdown"] == 0
        assert result["win_rate"] == 0

    def test_insufficient_equity_data(self):
        result = calculate_metrics([100000], [{"pnl_pct": 5, "hold_days": 5}], 100000)
        assert result["total_trades"] == 1
        assert result["annual_return"] == 0
        assert result["sharpe_ratio"] == 0

    def test_straight_up_market(self):
        equity = [100000, 101000, 102000, 103000, 104000, 105000]
        trades = [
            {"pnl_pct": 2.0, "hold_days": 3},
            {"pnl_pct": 3.0, "hold_days": 5},
        ]
        result = calculate_metrics(equity, trades, 100000)
        assert result["total_return"] == 5.0
        assert result["total_trades"] == 2
        assert result["win_rate"] == 100.0
        assert result["max_drawdown"] == 0.0
        assert result["annual_return"] > 0
        assert result["sharpe_ratio"] != 0

    def test_with_drawdown(self):
        equity = [100000, 105000, 102000, 108000, 103000, 110000]
        trades = [
            {"pnl_pct": 5.0, "hold_days": 2},
            {"pnl_pct": -3.0, "hold_days": 3},
            {"pnl_pct": 10.0, "hold_days": 7},
        ]
        result = calculate_metrics(equity, trades, 100000)
        assert result["total_return"] == 10.0
        assert result["total_trades"] == 3
        assert 0 < result["max_drawdown"] < 10
        assert result["win_rate"] == 66.7
        assert result["avg_hold_days"] is not None

    def test_max_drawdown_calculation(self):
        equity = [100000, 110000, 120000, 105000, 115000, 130000]
        trades = [{"pnl_pct": 10.0, "hold_days": 5}]
        result = calculate_metrics(equity, trades, 100000)
        peak = 120000
        trough = 105000
        expected_dd = round((peak - trough) / peak * 100, 2)
        assert result["max_drawdown"] == expected_dd

    def test_sharpe_with_negative_returns(self):
        equity = [100000, 99000, 101000, 98000, 102000, 97000]
        trades = [
            {"pnl_pct": -1.0, "hold_days": 2},
            {"pnl_pct": 2.0, "hold_days": 3},
            {"pnl_pct": -3.0, "hold_days": 4},
        ]
        result = calculate_metrics(equity, trades, 100000)
        assert result["total_trades"] == 3
        assert result["win_rate"] == 33.3
        assert isinstance(result["sharpe_ratio"], float)

    def test_annual_return_cagr(self):
        initial = 100000
        final = 121000
        equity = [initial, 105000, 110000, 115000, 118000, 121000]
        trades = [{"pnl_pct": 5.0, "hold_days": 5}]
        n_days = len(equity) - 1
        result = calculate_metrics(equity, trades, initial)
        expected_cagr = ((final / initial) ** (252.0 / n_days) - 1) * 100
        assert abs(result["annual_return"] - round(expected_cagr, 2)) < 0.01
