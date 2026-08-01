import requests


class TestSettingsE2E:

    def test_update_and_verify_persistence(self, api_url: str, auth_header: dict, clean_settings):
        resp = requests.put(f"{api_url}/settings", json={
            "site_name": "E2E测试系统",
            "site_description": "E2E test instance",
        }, headers=auth_header, timeout=10)
        assert resp.status_code == 200

        resp2 = requests.get(f"{api_url}/settings",
                             headers=auth_header, timeout=10)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["site_name"] == "E2E测试系统"
        assert data["site_description"] == "E2E test instance"

    def test_public_settings_does_not_expose_secrets(self, api_url: str, auth_header: dict, clean_settings):
        requests.put(f"{api_url}/settings", json={
            "llm_api_key": "sk-top-secret",
            "dingtalk_secret": "ding-secret-123",
        }, headers=auth_header, timeout=10)

        resp = requests.get(f"{api_url}/settings/public", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_api_key" not in data
        assert "dingtalk_secret" not in data

    def test_non_admin_cannot_update_settings(self, api_url: str):
        import random
        suffix = random.randint(10000, 99999)
        username = f"testuser_{suffix}"
        password = "testpass123"

        reg = requests.post(f"{api_url}/auth/register", json={
            "username": username,
            "password": password,
            "email": f"{username}@test.com",
        }, timeout=10)
        assert reg.status_code == 201

        login = requests.post(f"{api_url}/auth/login", json={
            "username": username,
            "password": password,
        }, timeout=10)
        assert login.status_code == 200
        user_token = login.json()["access_token"]

        resp = requests.put(f"{api_url}/settings", json={
            "site_name": "hacked",
        }, headers={"Authorization": f"Bearer {user_token}"}, timeout=10)
        assert resp.status_code == 403

    def test_put_with_null_fields_does_not_overwrite(self, api_url: str, auth_header: dict, clean_settings):
        requests.put(f"{api_url}/settings", json={"site_description": "original"},
                     headers=auth_header, timeout=10)
        requests.put(f"{api_url}/settings", json={"site_description": None},
                     headers=auth_header, timeout=10)

        resp = requests.get(f"{api_url}/settings",
                            headers=auth_header, timeout=10)
        data = resp.json()
        assert data["site_description"] == "original"

    def test_all_default_keys_present(self, api_url: str, admin_token):
        resp = requests.get(f"{api_url}/settings",
                            headers={"Authorization": f"Bearer {admin_token}"},
                            timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        for key in ("site_name", "site_status", "timezone", "date_format",
                     "llm_api_url", "llm_model", "session_expire_minutes"):
            assert key in data, f"Missing key: {key}"
            assert data[key] is not None, f"None value for: {key}"
