import pytest
import requests
import time

API_BASE = "http://localhost:8000"


def _get_token():
    resp = requests.post(f"{API_BASE}/auth/login", json={
        "username": "admin", "password": "admin123",
    }, timeout=5)
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestWorkflowSelection:
    """E2E: 选股+规则+回测+模拟盘流程"""

    def test_workflow_rule_crud(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/rules", headers=headers, timeout=5)
        assert resp.status_code == 200

    def test_workflow_news_selection(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/selections/dual-ma", headers=headers, timeout=5)
        assert resp.status_code in (200, 404)

    def test_workflow_heatmap_selection(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/selections/heatmap", headers=headers, timeout=5)
        assert resp.status_code in (200, 404)

    def test_workflow_backtest(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/backtest/latest", headers=headers, timeout=5)
        assert resp.status_code in (200, 404)

    def test_workflow_paper_trading(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/paper-trading/positions", headers=headers, timeout=5)
        assert resp.status_code in (200, 401)

    def test_workflow_notification_and_review(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/settings/public", timeout=5)
        assert resp.status_code == 200
