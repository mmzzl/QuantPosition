import requests


class TestAuthFlow:

    def test_login_with_valid_credentials(self, api_url: str, app_health):
        resp = requests.post(f"{api_url}/auth/login", json={
            "username": "admin",
            "password": "admin123",
        }, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["role"], str) and len(data["role"]) > 0

    def test_login_with_invalid_password(self, api_url: str, app_health):
        resp = requests.post(f"{api_url}/auth/login", json={
            "username": "admin",
            "password": "wrongpass",
        }, timeout=10)
        assert resp.status_code == 401
        assert "Incorrect" in resp.json()["detail"]

    def test_login_with_nonexistent_user(self, api_url: str, app_health):
        resp = requests.post(f"{api_url}/auth/login", json={
            "username": "nonexistent_user_12345",
            "password": "somepass",
        }, timeout=10)
        assert resp.status_code == 401

    def test_protected_endpoint_without_token_returns_401(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/settings", timeout=10)
        assert resp.status_code == 401

    def test_protected_endpoint_with_invalid_token_returns_401(self, api_url: str, app_health):
        resp = requests.get(f"{api_url}/settings",
                            headers={"Authorization": "Bearer invalidtoken"},
                            timeout=10)
        assert resp.status_code == 401

    def test_protected_endpoint_with_valid_token_succeeds(self, api_url: str, app_health, admin_token):
        resp = requests.get(f"{api_url}/settings",
                            headers={"Authorization": f"Bearer {admin_token}"},
                            timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "site_name" in data
        assert isinstance(data["site_name"], str) and len(data["site_name"]) > 0
