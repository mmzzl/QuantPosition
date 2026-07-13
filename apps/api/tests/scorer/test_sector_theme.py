import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch
from services.scorer.sector_theme import score_sector_theme, clear_cache


def setup_function():
    clear_cache()


MOCK_RANKINGS = {
    "rankings": {
        "银行": {"rank": 1, "return": 5.0, "total": 80},
        "非银金融": {"rank": 5, "return": 3.0, "total": 80},
        "医药生物": {"rank": 10, "return": 2.0, "total": 80},
        "食品饮料": {"rank": 15, "return": 1.5, "total": 80},
        "煤炭": {"rank": 30, "return": -2.0, "total": 80},
        "钢铁": {"rank": 50, "return": -4.0, "total": 80},
    },
    "_meta": {"total": 80},
}


def test_industry_top5():
    """Bank ranked #1, return > 3% → full 17pts"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = MOCK_RANKINGS
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["breakdown"]["industry_rank"] == 12
    assert result["breakdown"]["industry_return"] == 5
    assert result["total"] == 17


def test_industry_penalty():
    """Industry return < -3% → total = 0"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = MOCK_RANKINGS
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="B08", concepts=[])
    assert result["total"] == 0


def test_industry_not_in_rankings():
    """Industry not found in rankings → 0"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = MOCK_RANKINGS
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="Z99", concepts=[])
    assert result["breakdown"]["industry_rank"] == 0
    assert result["total"] == 0


def test_industry_no_industry_code():
    """No industry_code → 0"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = MOCK_RANKINGS
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code=None, concepts=[])
    assert result["total"] == 0


def test_industry_ranking_error():
    """Ranking computation fails → 0"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.side_effect = Exception("DB error")
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["total"] == 0


def test_industry_return_moderate():
    """Industry return between 1-3% → +3"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = {
            "rankings": {"银行": {"rank": 10, "return": 2.0, "total": 80}},
            "_meta": {"total": 80},
        }
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["breakdown"]["industry_return"] == 3
    assert result["breakdown"]["industry_rank"] == 8  # rank 10 → top 10


def test_industry_rank20():
    """Industry rank 11-20 → +4"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = {
            "rankings": {"银行": {"rank": 15, "return": 1.0, "total": 80}},
            "_meta": {"total": 80},
        }
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66", concepts=[])
    assert result["breakdown"]["industry_rank"] == 4
    assert result["breakdown"]["industry_return"] == 0  # return < 1%
    assert result["total"] == 4


def test_industry_prefix_extraction():
    """_extract_prefix handles mixed code+name format (J66金融业)"""
    with patch("services.scorer.sector_theme._compute_industry_rankings") as m:
        m.return_value = MOCK_RANKINGS
        result = score_sector_theme("000001", "2026-07-10",
                                    industry_code="J66金融业", concepts=[])
    assert result["total"] == 17  # should match to 银行
