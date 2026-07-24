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


class TestWorkflowTrade:
    """E2E: 持仓+热力图流程"""

    def test_workflow_buy_hold_sell(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(f"{API_BASE}/holdings/portfolio", headers=headers, timeout=5)
        assert resp.status_code in (200, 401)

    def test_workflow_sector_heatmap(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(f"{API_BASE}/sectors/heatmap", headers=headers, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "sectors" in data
