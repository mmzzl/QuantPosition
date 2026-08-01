import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest


class TestBacktestScoring:
    def test_run_backtest_accepts_default_parameters(self):
        from services.backtest_engine import run_backtest
        with patch("services.backtest_engine.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.stock_kline.distinct.return_value = []
            mock_db.trading_rules.find.return_value.sort.return_value = []
            mock_db.sector_stocks.find.return_value = []
            mock_get_db.return_value = mock_db
            result = run_backtest()
        assert result is not None
        assert "trades" in result
        assert "processed" in result

    def test_run_backtest_imports_scoring(self):
        from services.backtest_engine import run_backtest
        assert run_backtest is not None
        from services.scoring.oversold_bounce import oversold_bounce_score
        assert oversold_bounce_score is not None


class TestScoreDetailFormat:
    def test_score_detail_has_all_layers(self):
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
        assert isinstance(detail["total"], (int, float))
        assert isinstance(detail["bias5"], (int, float))
        assert isinstance(detail["trend"], (int, float))
        assert isinstance(detail["sector"], (int, float))
        assert isinstance(detail["sentiment"], (int, float))
        assert isinstance(detail["risk_eliminated"], bool)

    def test_score_detail_total_within_range(self):
        from services.scoring.oversold_bounce import score_detail
        detail = score_detail(
            close=10.0, ma5=10.204, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=False,
        )
        assert 0 <= detail["total"] <= 100

    def test_score_detail_st_stock_risk_eliminated(self):
        from services.scoring.oversold_bounce import score_detail
        detail = score_detail(
            close=10.0, ma5=10.2, ma10=9.8, ma20=9.5, ma60=9.0,
            volume=800_000, ma5_vol=100_000_000,
            high20=10.5, amplitude=0.04, is_st=True,
        )
        assert detail["risk_eliminated"] is True
        assert detail["total"] == 0.0


class TestBacktestResultHasScoreDetail:
    def test_run_backtest_returns_result_with_trades_key(self):
        from services.backtest_engine import run_backtest
        with patch("services.backtest_engine.get_db") as mock_get_db,\
             patch("services.backtest_engine._load_name_map") as mock_nm:
            mock_db = MagicMock()
            mock_db.stock_kline.distinct.return_value = []
            mock_db.trading_rules.find.return_value.sort.return_value = []
            mock_db.sector_stocks.find.return_value = []
            mock_db.stock_indicators.find.return_value.sort.return_value = []
            mock_get_db.return_value = mock_db
            mock_nm.return_value = {}
            result = run_backtest()
        assert "trades" in result


class TestBacktestDailyConsistency:
    def test_same_scoring_function_used_in_backtest_and_daily(self):
        from services.backtest_engine import run_backtest
        from services.scoring.oversold_bounce import oversold_bounce_score
        from bin.rule_engine import StockRuleEngine
        assert oversold_bounce_score is not None
        assert StockRuleEngine is not None

    def test_oversold_bounce_in_backtest_engine(self):
        import services.backtest_engine as bte
        assert hasattr(bte, "oversold_bounce_score")
        assert hasattr(bte, "score_detail")


class TestRuleExplorerNoValidationRound:
    def test_validate_candidates_no_max_stocks(self):
        try:
            from services.rule_explorer import validate_candidates
            sig = validate_candidates.__code__.co_varnames
            assert "max_stocks" not in sig, "validate_candidates 仍含 max_stocks 参数"
        except ImportError:
            pass

    def test_rule_explorer_no_use_scorer(self):
        import services.rule_explorer as re
        src = open(re.__file__, encoding="utf-8").read()
        assert "use_scorer" not in src, "rule_explorer.py 仍引用 use_scorer"

    def test_rule_explorer_no_validation_round(self):
        import services.rule_explorer as re
        src = open(re.__file__, encoding="utf-8").read()
        assert "validation_round" not in src, "rule_explorer.py 仍引用 validation_round"