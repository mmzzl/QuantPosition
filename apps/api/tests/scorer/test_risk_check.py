import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch
import pandas as pd
from services.scorer.risk_check import score_risk, clear_cache


def setup_function():
    clear_cache()


def test_clean_stock():
    with patch("services.scorer.risk_check.akshare") as mock_ak:
        mock_ak.stock_restricted_release_detail_em.return_value = pd.DataFrame()
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 5


def test_st_stock():
    with patch("services.scorer.risk_check.akshare") as mock_ak:
        result = score_risk("600001", "ST华业", "2026-07-10")
    assert result["total"] == 0
    assert result["veto"] is True


def test_delisting_risk():
    with patch("services.scorer.risk_check.akshare") as mock_ak:
        mock_ak.stock_restricted_release_detail_em.return_value = pd.DataFrame()
        result = score_risk("000001", "TestCorp", "2026-07-10", delisting_risk=True)
    assert result["total"] == 0
    assert result["veto"] is True


def test_restricted_release_today():
    data = {"解禁日期": ["2026-07-10"], "股票代码": ["000001"], "股票简称": ["Test"]}
    with patch("services.scorer.risk_check.akshare") as mock_ak:
        mock_ak.stock_restricted_release_detail_em.return_value = pd.DataFrame(data)
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 4  # ST(2) + delist(2) = 4, bad_news=0


def test_name_with_star_st():
    for name in ["*ST信威", "退市金钰"]:
        result = score_risk("000001", name, "2026-07-10")
        assert result["total"] == 0, f"Failed for name: {name}"


def test_api_error_default_pass():
    with patch("services.scorer.risk_check.akshare") as mock_ak:
        mock_ak.stock_restricted_release_detail_em.side_effect = Exception("API error")
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 5  # API fails → default pass
