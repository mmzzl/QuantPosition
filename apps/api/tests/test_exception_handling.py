import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from services.scoring.oversold_bounce import (
    oversold_bounce_score,
    _layer2_bias5_score,
    _layer4_sector_score,
)


class TestDataAnomalies:
    def test_insufficient_klines_returns_zero(self):
        score = oversold_bounce_score(
            close=10.0, ma5=0, ma10=9.5, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == -1.0

    def test_layer2_independent_zero(self):
        score = _layer2_bias5_score(close=10.0, ma5=0, volume=800_000, ma5_vol=1_000_000)
        assert score == 0.0

    def test_close_zero_returns_negative_one(self):
        score = oversold_bounce_score(
            close=0, ma5=10.0, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == -1.0

    def test_volume_zero_volume_factor_defaults_08(self):
        # Spec section 3 exception table: volume=0 (suspension) -> Layer 1 eliminates, returns -1
        score = oversold_bounce_score(
            close=9.75, ma5=10.0, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=0, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == -1.0

    def test_volume_zero_layer2_still_runs_for_unit(self):
        # _layer2_bias5_score is a pure function; when called directly with volume=0,
        # spec EX-004 says BIAS5 normal scoring with factor 0.8 (back-compat for unit tests)
        score = _layer2_bias5_score(close=9.75, ma5=10.0, volume=0, ma5_vol=1_000_000)
        assert score == pytest.approx(20.0, rel=1e-6)

    def test_ma5_none_skips_elimination_returns_zero(self):
        # Spec section 4.2: missing data in Layer 1 -> don't eliminate, return 0
        score = oversold_bounce_score(
            close=10.0, ma5=None, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == 0.0

    def test_ma5_vol_none_skips_returns_zero(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.0, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=None,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == 0.0

    def test_volume_none_skips_returns_zero(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.0, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=None, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == 0.0

    def test_nan_input_returns_zero(self):
        import math
        score = oversold_bounce_score(
            close=10.0, ma5=math.nan, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == 0.0

    def test_no_sector_defaults_5(self):
        assert _layer4_sector_score(capital_flow_status=None) == 5.0

    def test_bias5_exact_minus2_scores_max(self):
        score = _layer2_bias5_score(close=9.8, ma5=10.0, volume=1_000_000, ma5_vol=1_000_000)
        assert score == pytest.approx(50.0, rel=1e-6)

    def test_bias5_midpoint_scores_half(self):
        score = _layer2_bias5_score(close=9.75, ma5=10.0, volume=1_000_000, ma5_vol=1_000_000)
        assert score == pytest.approx(25.0, rel=1e-6)

    def test_bias5_exact_minus3_scores_0(self):
        score = _layer2_bias5_score(close=9.7, ma5=10.0, volume=800_000, ma5_vol=1_000_000)
        assert score == 0.0

    def test_all_zero_scenario(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.0, ma10=10.0, ma20=10.1, ma60=10.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score <= 15.0


class TestSystemExceptions:
    def test_st_stock_eliminated(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=True,
        )
        assert score == -1.0

    def test_low_price_eliminated(self):
        score = oversold_bounce_score(
            close=1.5, ma5=1.6, ma10=1.55, ma20=1.5, ma60=1.4,
            volume=800_000, ma5_vol=100_000_000,
            high20=1.8, amplitude=0.04, is_st=False,
        )
        assert score == -1.0

    def test_low_liquidity_eliminated(self):
        # ma5_vol 单位手：20,000手 × 100股 × close=10 ≈ 2000万 < 5000万 → 低流动性剔除
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=20_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == -1.0

    def test_liquidity_passes_high_turnover(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score != -1.0

    def test_bias5_below_neg3_not_selected(self):
        score = oversold_bounce_score(
            close=9.6, ma5=10.0, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert score == 0.0

    def test_score_detail_not_affected_by_exception_in_layer(self):
        from services.scoring.oversold_bounce import score_detail
        detail = score_detail(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert "total" in detail
        assert "bias5" in detail
        assert "trend" in detail
        assert "sector" in detail
        assert "sentiment" in detail
        assert "risk_eliminated" in detail
        assert detail["risk_eliminated"] is False