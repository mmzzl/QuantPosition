import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from unittest.mock import patch, MagicMock
import json
from services.scorer.risk_check import score_risk, clear_cache


def _mock_org_map():
    return {"stockList": [{"code": "000001", "orgId": "test_org_001"}]}


def setup_function():
    clear_cache()


def test_clean_stock():
    with patch("services.scorer.risk_check.requests") as mock_req:
        mock_req.get.return_value.ok = True
        mock_req.get.return_value.json.return_value = _mock_org_map()
        mock_req.post.return_value.ok = True
        mock_req.post.return_value.json.return_value = {"announcements": []}
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 5


def test_st_stock():
    result = score_risk("600001", "ST华业", "2026-07-10")
    assert result["total"] == 0
    assert result["veto"] is True


def test_delisting_risk():
    with patch("services.scorer.risk_check.requests") as mock_req:
        mock_req.get.return_value.ok = True
        mock_req.get.return_value.json.return_value = _mock_org_map()
        mock_req.post.return_value.ok = True
        mock_req.post.return_value.json.return_value = {"announcements": []}
        result = score_risk("000001", "TestCorp", "2026-07-10", delisting_risk=True)
    assert result["total"] == 0
    assert result["veto"] is True


def test_restricted_release_today():
    with patch("services.scorer.risk_check.requests") as mock_req:
        mock_req.get.return_value.ok = True
        mock_req.get.return_value.json.return_value = _mock_org_map()
        mock_req.post.return_value.ok = True
        mock_req.post.return_value.json.return_value = {
            "announcements": [{"announcementTitle": "限售股份上市流通提示性公告"}]
        }
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 4  # ST(2) + delist(2) = 4, bad_news=0


def test_name_with_star_st():
    for name in ["*ST信威", "退市金钰"]:
        result = score_risk("000001", name, "2026-07-10")
        assert result["total"] == 0, f"Failed for name: {name}"


def test_api_error_default_pass():
    with patch("services.scorer.risk_check.requests") as mock_req:
        mock_req.get.return_value.ok = True
        mock_req.get.return_value.json.return_value = _mock_org_map()
        mock_req.post.side_effect = Exception("cninfo API error")
        result = score_risk("000001", "TestCorp", "2026-07-10")
    assert result["total"] == 5  # cninfo API fails → default pass
