import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch
import pandas as pd
from services.scorer.sector_theme import score_sector_theme, clear_cache


def setup_function():
    clear_cache()


def _mock_industry_df(keywords_top):
    data = {
        "行业": [kw[0] for kw in keywords_top],
        "行业指数": [10.0] * len(keywords_top),
        "阶段涨跌幅": [f"{kw[1]:.2f}%" for kw in keywords_top],
        "净额": [kw[2] for kw in keywords_top],
    }
    return pd.DataFrame(data)


def _mock_concept_df(keywords_top):
    data = {
        "概念": [kw[0] for kw in keywords_top],
        "概念指数": [10.0] * len(keywords_top),
        "概念-涨跌幅": [f"{kw[1]:.2f}%" for kw in keywords_top],
        "净额": [kw[2] for kw in keywords_top],
    }
    return pd.DataFrame(data)


def test_industry_top5():
    """Industry (bank) is rank 1 (top 5), return > 3%"""
    with patch("services.scorer.sector_theme.akshare") as mock_ak:
        mock_ak.stock_fund_flow_industry.return_value = _mock_industry_df([
            ("银行", 3.5, 5_000_000_000),
        ])
        mock_ak.stock_fund_flow_concept.return_value = _mock_concept_df([])
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["breakdown"]["industry_rank"] == 12
    assert result["breakdown"]["industry_return"] == 5
    assert result["breakdown"]["concept"] == 0
    assert result["total"] == 17


def test_industry_penalty():
    """Industry return < -3% -> total = 0"""
    with patch("services.scorer.sector_theme.akshare") as mock_ak:
        mock_ak.stock_fund_flow_industry.return_value = _mock_industry_df([
            ("银行", -4.0, -1_000_000_000),
        ])
        mock_ak.stock_fund_flow_concept.return_value = _mock_concept_df([])
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["total"] == 0


def test_industry_not_matched():
    """Industry not found in ranking -> 0"""
    with patch("services.scorer.sector_theme.akshare") as mock_ak:
        mock_ak.stock_fund_flow_industry.return_value = _mock_industry_df([
            ("医药生物", 2.0, 2_000_000_000),
        ])
        mock_ak.stock_fund_flow_concept.return_value = _mock_concept_df([])
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["breakdown"]["industry_rank"] == 0
    assert result["total"] == 0


def test_api_error():
    """All APIs fail -> total = 0"""
    with patch("services.scorer.sector_theme.akshare") as mock_ak:
        mock_ak.stock_fund_flow_industry.side_effect = Exception("API error")
        mock_ak.stock_fund_flow_concept.side_effect = Exception("API error")
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["total"] == 0


def test_concept_hot():
    """Stock concept matched in top 5 -> +3"""
    with patch("services.scorer.sector_theme.akshare") as mock_ak:
        mock_ak.stock_fund_flow_industry.return_value = _mock_industry_df([])
        mock_ak.stock_fund_flow_concept.return_value = _mock_concept_df([
            ("国企改革", 3.0, 2_000_000_000),
            ("数字经济", 4.0, 3_000_000_000),
        ])
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code=None, concepts=["国企改革"])
    assert result["breakdown"]["concept"] == 3


def test_moderate_return():
    """Industry return between 1-3% -> +3"""
    with patch("services.scorer.sector_theme.akshare") as mock_ak:
        mock_ak.stock_fund_flow_industry.return_value = _mock_industry_df([
            ("银行", 2.0, 5_000_000_000),
        ])
        mock_ak.stock_fund_flow_concept.return_value = _mock_concept_df([])
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["breakdown"]["industry_return"] == 3
