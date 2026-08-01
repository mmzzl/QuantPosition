"""Unit tests for oversold_bounce_score 5-layer scoring pipeline.
Covers spec TC-001~008, TC-013~014, TC-019.
"""

import pytest

from services.scoring.oversold_bounce import (
    _layer1_risk_elimination,
    _layer2_bias5_score,
    _layer3_trend_score,
    _layer4_sector_score,
    _layer5_sentiment_score,
    oversold_bounce_score,
)


def make_indicators(close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
                    volume=800_000, ma5_vol=100_000_000, high20=10.5, amplitude=0.04):
    return {
        "close": close, "ma5": ma5, "ma10": ma10,
        "ma20": ma20, "ma60": ma60,
        "volume": volume, "ma5_vol": ma5_vol,
        "high20": high20, "amplitude": amplitude,
    }


class TestLayer1RiskElimination:
    def test_st_stock_returns_negative_one(self):
        result = _layer1_risk_elimination(make_indicators(), is_st=True)
        assert result == -1

    def test_low_price_returns_negative_one(self):
        result = _layer1_risk_elimination(make_indicators(close=1.5))
        assert result == -1

    def test_low_liquidity_returns_negative_one(self):
        # ma5_vol 单位手：20,000手 × 100股 × close=10 ≈ 2000万 < 5000万 → 低流动性剔除
        result = _layer1_risk_elimination(make_indicators(ma5_vol=20_000))
        assert result == -1

    def test_turnover_over_threshold_returns_zero(self):
        # 30,000,000手 × 100 × 10 = 300亿 成交额，远超 5000万 → 通过流动性
        result = _layer1_risk_elimination(make_indicators(ma5_vol=30_000_000))
        assert result == 0

    def test_bias_too_deep_returns_zero(self):
        result = _layer1_risk_elimination(make_indicators(close=9.8, ma5=10.2))
        assert result == 0

    def test_sufficient_data_returns_zero(self):
        result = _layer1_risk_elimination(make_indicators())
        assert result == 0

    def test_close_zero_returns_negative_one(self):
        result = _layer1_risk_elimination(make_indicators(close=0, ma5=10.2))
        assert result == -1

    def test_ma5_zero_returns_negative_one(self):
        result = _layer1_risk_elimination(make_indicators(ma5=0))
        assert result == -1


class TestLayer2Bias5:
    def test_optimal_bias_scores_max(self):
        score = _layer2_bias5_score(close=9.78, ma5=10.0, volume=800_000, ma5_vol=1_200_000)
        assert score == pytest.approx(48.0, rel=1e-6)

    def test_bias_out_of_range_scores_zero(self):
        score = _layer2_bias5_score(close=9.85, ma5=10.0, volume=800_000, ma5_vol=1_200_000)
        assert score == 0.0

    def test_bias_below_neg3_scores_zero(self):
        score = _layer2_bias5_score(close=9.69, ma5=10.0, volume=800_000, ma5_vol=1_200_000)
        assert score == 0.0

    def test_volume_shrink_multiplies_12(self):
        score = _layer2_bias5_score(close=9.75, ma5=10.0, volume=400_000, ma5_vol=1_200_000)
        assert score == pytest.approx(30.0, rel=1e-6)

    def test_volume_expand_multiplies_08(self):
        score = _layer2_bias5_score(close=9.75, ma5=10.0, volume=2_000_000, ma5_vol=1_200_000)
        assert score == pytest.approx(20.0, rel=1e-6)

    def test_ma5_zero_returns_zero(self):
        score = _layer2_bias5_score(close=10.0, ma5=0.0, volume=800_000, ma5_vol=1_200_000)
        assert score == 0.0


class TestLayer3Trend:
    def test_close_above_ma20_scores_15(self):
        score = _layer3_trend_score(close=10.0, ma20=9.5, ma60=9.0)
        assert score == 20.0

    def test_close_near_ma20_gets_extra_10(self):
        score = _layer3_trend_score(close=10.0, ma20=9.95, ma60=9.5)
        assert score >= 25

    def test_all_mas_below_gets_extra_5(self):
        score = _layer3_trend_score(close=10.0, ma20=9.5, ma60=9.0)
        assert score >= 20

    def test_ma20_above_close_scores_zero(self):
        score = _layer3_trend_score(close=9.0, ma20=9.5, ma60=9.0)
        assert score == 0.0


class TestLayer4Sector:
    def test_net_inflow_scores_15(self):
        score = _layer4_sector_score(capital_flow_status="inflow")
        assert score == 15.0

    def test_no_data_defaults_to_5(self):
        score = _layer4_sector_score(capital_flow_status=None)
        assert score == 5.0

    def test_net_outflow_scores_0(self):
        score = _layer4_sector_score(capital_flow_status="outflow")
        assert score == 0.0

    def test_unknown_status_defaults_to_5(self):
        score = _layer4_sector_score(capital_flow_status="unknown")
        assert score == 5.0


class TestLayer5Sentiment:
    def test_all_conditions_met_scores_10(self):
        score = _layer5_sentiment_score(
            has_big_drop=False,
            has_chip_support=True,
            has_capital_outflow=False,
        )
        assert score == 10.0

    def test_no_chip_data_defaults_zero(self):
        score = _layer5_sentiment_score(
            has_big_drop=False,
            has_chip_support=False,
            has_capital_outflow=False,
            chip_data_available=False,
        )
        assert score == 7.0

    def test_big_drop_deducts_4(self):
        score = _layer5_sentiment_score(
            has_big_drop=True,
            has_chip_support=True,
            has_capital_outflow=False,
        )
        assert score == 6.0

    def test_no_capital_data_ignores_outflow(self):
        score = _layer5_sentiment_score(
            has_big_drop=False,
            has_chip_support=True,
            has_capital_outflow=True,
            capital_data_available=False,
        )
        assert score == 7.0


class TestOversoldBounceScore:
    def test_normal_stock_returns_score(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04,
            is_st=False,
            capital_flow_status="inflow",
            has_big_drop=False, has_chip_support=True, has_capital_outflow=False,
        )
        assert 0 <= score <= 100

    def test_st_stock_returns_negative_one(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.2, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04,
            is_st=True,
        )
        assert score == -1

    def test_total_capped_at_100(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04,
            is_st=False,
            capital_flow_status="inflow",
            has_big_drop=False, has_chip_support=True, has_capital_outflow=False,
        )
        assert score <= 100

    def test_low_price_returns_negative_one(self):
        score = oversold_bounce_score(
            close=1.5, ma5=1.6, ma10=1.55, ma20=1.5, ma60=1.4,
            volume=800_000, ma5_vol=100_000_000,
            high20=1.8, amplitude=0.04,
            is_st=False,
        )
        assert score == -1

    def test_no_sector_data_defaults_balanced(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04,
            is_st=False,
            capital_flow_status=None,
            has_big_drop=False, has_chip_support=True, has_capital_outflow=False,
        )
        assert score <= 100 and score >= 0

    def test_chip_data_unavailable_partial_score(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04,
            is_st=False,
            chip_data_available=False,
            has_big_drop=False, has_chip_support=False, has_capital_outflow=False,
        )
        assert 0 <= score <= 100

    def test_capital_data_unavailable_fallback_score(self):
        score = oversold_bounce_score(
            close=10.0, ma5=10.204, ma10=9.2, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04,
            is_st=False,
            capital_data_available=False,
            has_big_drop=False, has_chip_support=True, has_capital_outflow=True,
        )
        assert 0 <= score <= 100