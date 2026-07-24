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


class TestPerformance:
    """E2E: 性能基准测试"""

    def test_auth_login_performance(self):
        start = time.time()
        for _ in range(5):
            requests.post(f"{API_BASE}/auth/login", json={
                "username": "admin", "password": "admin123",
            }, timeout=5)
        elapsed = time.time() - start
        avg = elapsed / 5
        assert avg < 2.0, f"Auth login avg {avg:.2f}s > 2s"

    def test_sector_heatmap_performance(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        start = time.time()
        resp = requests.get(f"{API_BASE}/sectors/heatmap", headers=headers, timeout=30)
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 10.0, f"Heatmap took {elapsed:.2f}s > 10s"

    def test_holdings_portfolio_performance(self):
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}
        start = time.time()
        resp = requests.get(f"{API_BASE}/holdings/portfolio", headers=headers, timeout=30)
        elapsed = time.time() - start
        assert resp.status_code in (200, 404)
        assert elapsed < 5.0, f"Portfolio took {elapsed:.2f}s > 5s"
