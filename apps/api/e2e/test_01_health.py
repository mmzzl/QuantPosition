import requests


class TestHealthEndpoint:

    def test_root_returns_site_name(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "持仓管理" in data["message"] or "running" in data["message"]

    def test_health_returns_healthy(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_cors_headers_present(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/",
                            headers={"Origin": "http://localhost:5173"},
                            timeout=10)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") is not None

    def test_404_returns_json(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/nonexistent", timeout=10)
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_public_settings_accessible_without_auth(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/settings/public", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "site_name" in data
        assert isinstance(data["site_name"], str) and len(data["site_name"]) > 0
        assert "llm_api_key" not in data
        assert "dingtalk_secret" not in data
