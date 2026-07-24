import pytest
import requests
import time

API_BASE = "http://localhost:8000"
SKIP_REASON = "需要 MongoDB 运行"


def _get_token():
    resp = requests.post(f"{API_BASE}/auth/login", json={
        "username": "admin", "password": "admin123",
    }, timeout=5)
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestWorkflowAuth:
    """E2E: 认证流程"""

    def test_workflow_register_login_menu(self):
        token = _get_token()
        resp = requests.get(f"{API_BASE}/menu", headers={
            "Authorization": f"Bearer {token}"
        }, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "menu" in data
        assert "authority_prms" in data

    def test_workflow_auth_errors(self):
        resp = requests.post(f"{API_BASE}/auth/login", json={
            "username": "nonexistent", "password": "wrong",
        }, timeout=5)
        assert resp.status_code == 401

        resp = requests.get(f"{API_BASE}/users", timeout=5)
        assert resp.status_code == 401

    def test_workflow_settings_public(self):
        resp = requests.get(f"{API_BASE}/settings/public", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "site_name" in data
