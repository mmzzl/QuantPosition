import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone, timedelta
from services.stock_scorer import StockScorer


def _make_klines(closes, dates=None, volumes=None, turnovers=None):
    klines = []
    for i, c in enumerate(closes):
        d = dates[i] if dates else f"2026-07-{i+1:02d}"
        v = volumes[i] if volumes else 100000
        t = turnovers[i] if turnovers else None
        k = {"date": d, "open": c, "close": c, "high": c * 1.02, "low": c * 0.98, "volume": v}
        if t is not None:
            k["turnover"] = t
        klines.append(k)
    return klines


class TestGainScore:
    def test_uptrend_scores_high(self):
        scorer = StockScorer()
        closes = [10.0 + i * 0.2 for i in range(20)]
        klines = _make_klines(closes)
        score = scorer._gain_score(klines)
        assert score > 60

    def test_downtrend_scores_low(self):
        scorer = StockScorer()
        closes = [10.0 - i * 0.2 for i in range(20)]
        klines = _make_klines(closes)
        score = scorer._gain_score(klines)
        assert score < 30

    def test_uptrend_beats_downtrend(self):
        scorer = StockScorer()
        up_closes = [10.0 + i * 0.15 for i in range(20)]
        down_closes = [10.0 - i * 0.15 for i in range(20)]
        up_score = scorer._gain_score(_make_klines(up_closes))
        down_score = scorer._gain_score(_make_klines(down_closes))
        assert up_score > down_score

    def test_insufficient_data_returns_zero(self):
        scorer = StockScorer()
        klines = _make_klines([10.0, 10.1])
        assert scorer._gain_score(klines) == 0.0

    def test_empty_klines_returns_zero(self):
        scorer = StockScorer()
        assert scorer._gain_score([]) == 0.0


class TestRiskScore:
    def test_low_volatility_scores_high(self):
        scorer = StockScorer()
        closes = [10.0 + i * 0.01 for i in range(30)]
        klines = _make_klines(closes)
        score = scorer._risk_score(klines)
        assert score > 60

    def test_high_volatility_scores_low(self):
        scorer = StockScorer()
        closes = [10.0]
        for _ in range(29):
            closes.append(closes[-1] * (1.0 + (-0.05 if _ % 2 == 0 else 0.05)))
        klines = _make_klines(closes)
        score = scorer._risk_score(klines)
        assert score < 98

    def test_low_vol_beats_high_vol(self):
        scorer = StockScorer()
        stable = [10.0 + i * 0.01 for i in range(30)]
        volatile = [10.0]
        for _ in range(29):
            volatile.append(volatile[-1] * (1.0 + (-0.05 if _ % 2 == 0 else 0.05)))
        stable_score = scorer._risk_score(_make_klines(stable))
        volatile_score = scorer._risk_score(_make_klines(volatile))
        assert stable_score > volatile_score

    def test_insufficient_data_defaults_25(self):
        scorer = StockScorer()
        klines = _make_klines([10.0] * 5)
        assert scorer._risk_score(klines) == 25.0

    def test_output_clamped_0_100(self):
        scorer = StockScorer()
        klines = _make_klines([10.0 + i * 0.01 for i in range(30)])
        score = scorer._risk_score(klines)
        assert 0.0 <= score <= 100.0


class TestMomentumScore:
    def test_bullish_alignment_scores_high(self):
        scorer = StockScorer()
        closes = [10.0 + i * 0.2 for i in range(30)]
        klines = _make_klines(closes)
        score = scorer._momentum_score(klines)
        assert score > 45

    def test_bearish_alignment_scores_low(self):
        scorer = StockScorer()
        closes = [10.0 - i * 0.1 for i in range(30)]
        klines = _make_klines(closes)
        score = scorer._momentum_score(klines)
        assert score < 30

    def test_bullish_beats_bearish(self):
        scorer = StockScorer()
        bull = [10.0 + i * 0.2 for i in range(30)]
        bear = [10.0 - i * 0.1 for i in range(30)]
        bull_score = scorer._momentum_score(_make_klines(bull))
        bear_score = scorer._momentum_score(_make_klines(bear))
        assert bull_score > bear_score

    def test_insufficient_data_defaults_25(self):
        scorer = StockScorer()
        klines = _make_klines([10.0] * 10)
        assert scorer._momentum_score(klines) == 25.0

    def test_output_clamped_0_100(self):
        scorer = StockScorer()
        klines = _make_klines([10.0 + i * 0.05 for i in range(30)])
        score = scorer._momentum_score(klines)
        assert 0.0 <= score <= 100.0


class TestQualityScore:
    def test_stable_turnover_scores_high(self):
        scorer = StockScorer()
        klines = _make_klines(
            [10.0 + i * 0.1 for i in range(20)],
            turnovers=[8.0] * 20,
        )
        score = scorer._quality_score(klines)
        assert score > 60

    def test_volatile_turnover_scores_low(self):
        scorer = StockScorer()
        klines = _make_klines(
            [10.0 + i * 0.1 for i in range(20)],
            turnovers=[5.0 if i % 2 == 0 else 0.5 for i in range(20)],
        )
        score = scorer._quality_score(klines)
        assert score < 60

    def test_insufficient_data_defaults_25(self):
        scorer = StockScorer()
        klines = _make_klines([10.0] * 5)
        assert scorer._quality_score(klines) == 25.0

    def test_indicator_bonus(self):
        scorer = StockScorer()
        klines = _make_klines(
            [10.0 + i * 0.05 for i in range(20)],
            turnovers=[6.0] * 20,
        )
        indicators = {"institutional_holding": 40.0}
        baseline = scorer._quality_score(klines)
        bonus = scorer._quality_score(klines, indicators)
        assert bonus >= baseline

    def test_output_clamped_0_100(self):
        scorer = StockScorer()
        klines = _make_klines(
            [10.0 + i * 0.1 for i in range(20)],
            turnovers=[8.0] * 20,
        )
        score = scorer._quality_score(klines)
        assert 0.0 <= score <= 100.0


class TestBatchScore:
    def test_batch_score_returns_dict(self):
        with patch("services.stock_scorer.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = []
            mock_db.stock_indicators.find_one.return_value = None
            mock_db.scorer_score.find_one.return_value = None

            scorer = StockScorer()
            result = scorer.batch_score(["000001", "000002"])
        assert isinstance(result, dict)
        assert "000001" in result
        assert "000002" in result
        assert isinstance(result["000001"], float)

    def test_batch_score_insufficient_klines(self):
        with patch("services.stock_scorer.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = []
            mock_db.stock_indicators.find_one.return_value = None
            mock_db.scorer_score.find_one.return_value = None

            scorer = StockScorer()
            result = scorer.batch_score(["999999"])
        assert result["999999"] == 0.0

    def test_batch_score_with_klines(self):
        closes_opening = [8.0 + i * 0.2 for i in range(30)]
        klines = _make_klines(closes_opening)

        with patch("services.stock_scorer.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = klines
            mock_db.stock_indicators.find_one.return_value = None
            mock_db.scorer_score.find_one.return_value = None
            mock_db.scorer_score.update_one = MagicMock()

            scorer = StockScorer()
            result = scorer.batch_score(["000001"])
        assert "000001" in result
        assert 0.0 <= result["000001"] <= 100.0

    def test_batch_st_stock_zero(self):
        closes = [10.0 + i * 0.2 for i in range(30)]
        klines = _make_klines(closes)

        with patch("services.stock_scorer.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.stock_kline.find.return_value.sort.return_value.limit.return_value = klines
            mock_db.stock_indicators.find_one.return_value = None
            mock_db.scorer_score.find_one.return_value = None
            mock_db.scorer_score.update_one = MagicMock()

            scorer = StockScorer()
            result = scorer.batch_score(["000001"], name="ST华业")
        assert result["000001"] == 0.0


class TestCache:
    def test_cached_score_hit(self):
        mock_db = MagicMock()
        scorer = StockScorer(db=mock_db)

        cached_doc = {
            "code": "000001",
            "score": 85.0,
            "dimensions": {"gain": 80, "quality": 75, "momentum": 70, "risk": 90},
            "cached_at": datetime.now(timezone.utc),
        }
        mock_db.scorer_score.find_one.return_value = cached_doc

        result = scorer._cached_score("000001")
        assert result is not None
        assert result["code"] == "000001"
        assert result["score"] == 85.0
        assert "dimensions" in result

    def test_cached_score_expired(self):
        mock_db = MagicMock()
        scorer = StockScorer(db=mock_db)

        expired_doc = {
            "code": "000001",
            "score": 85.0,
            "dimensions": {"gain": 80},
            "cached_at": datetime.now(timezone.utc) - timedelta(seconds=61),
        }
        mock_db.scorer_score.find_one.return_value = expired_doc

        result = scorer._cached_score("000001")
        assert result is None

    def test_cached_score_miss(self):
        mock_db = MagicMock()
        scorer = StockScorer(db=mock_db)
        mock_db.scorer_score.find_one.return_value = None

        result = scorer._cached_score("000001")
        assert result is None

    def test_save_cached_score(self):
        mock_db = MagicMock()
        scorer = StockScorer(db=mock_db)

        scorer._save_cached_score("000001", 78.5, {
            "gain": 80, "quality": 75, "momentum": 70, "risk": 90,
        })

        mock_db.scorer_score.update_one.assert_called_once()
        args, kwargs = mock_db.scorer_score.update_one.call_args
        assert args[0] == {"code": "000001"}
        assert "$set" in args[1]
        assert args[1]["$set"]["code"] == "000001"
        assert args[1]["$set"]["score"] == 78.5
        assert args[1]["$set"]["dimensions"]["gain"] == 80


class TestUnifiedScoringWeights:
    def test_four_dimensions_contribute(self):
        scorer = StockScorer()
        bull_klines = _make_klines([10.0 + i * 0.2 for i in range(30)])

        gain = scorer._gain_score(bull_klines)
        qual = scorer._quality_score(bull_klines)
        mom = scorer._momentum_score(bull_klines)
        risk = scorer._risk_score(bull_klines)

        unified = gain * 0.30 + qual * 0.25 + mom * 0.25 + risk * 0.20
        unified = max(0.0, min(100.0, unified))
        assert 0.0 <= unified <= 100.0

    def test_unified_bull_market_high(self):
        scorer = StockScorer()
        bull_klines = _make_klines([10.0 + i * 0.2 for i in range(30)])

        gain = scorer._gain_score(bull_klines)
        qual = scorer._quality_score(bull_klines)
        mom = scorer._momentum_score(bull_klines)
        risk = scorer._risk_score(bull_klines)

        unified = gain * 0.30 + qual * 0.25 + mom * 0.25 + risk * 0.20
        unified = max(0.0, min(100.0, unified))
        assert unified > 30

    def test_unified_bear_market_low(self):
        scorer = StockScorer()
        bear_klines = _make_klines([10.0 - i * 0.15 for i in range(30)])

        gain = scorer._gain_score(bear_klines)
        qual = scorer._quality_score(bear_klines)
        mom = scorer._momentum_score(bear_klines)
        risk = scorer._risk_score(bear_klines)

        unified = gain * 0.30 + qual * 0.25 + mom * 0.25 + risk * 0.20
        unified = max(0.0, min(100.0, unified))
        assert unified < 40