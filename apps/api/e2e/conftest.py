import pytest
import requests
import time
import random
import string

API_BASE = "http://localhost:8000"


@pytest.fixture(scope="session")
def api_url() -> str:
    return API_BASE


@pytest.fixture(scope="session")
def app_health(api_url: str) -> None:
    deadline = time.time() + 30
    last_exc = None
    while time.time() < deadline:
        try:
            resp = requests.get(f"{api_url}/health", timeout=5)
            if resp.status_code == 200:
                return
        except requests.RequestException as e:
            last_exc = e
        time.sleep(1)
    pytest.fail(f"App not healthy after 30s: {last_exc}")


def _ensure_admin(api_url: str) -> str:
    """Return (username, password, token) for a working admin user."""
    candidates = [
        ("admin", "admin123"),
        ("admin", "admin"),
        ("admin", "password"),
    ]
    for username, password in candidates:
        resp = requests.post(f"{api_url}/auth/login", json={
            "username": username, "password": password,
        })
        if resp.status_code == 200:
            return resp.json()["access_token"]

    suffix = random.randint(10000, 99999)
    username = f"e2e_admin_{suffix}"
    password = "e2e_pass_123"
    resp = requests.post(f"{api_url}/auth/register", json={
        "username": username, "password": password,
        "email": f"{username}@e2e.local",
    })
    if resp.status_code == 201:
        login = requests.post(f"{api_url}/auth/login", json={
            "username": username, "password": password,
        })
        if login.status_code == 200:
            return login.json()["access_token"]
    user_info = f"register={resp.status_code}, login={login.status_code if 'login' in dir() else 'N/A'}"
    pytest.fail(f"Cannot obtain admin access. Tried existing accounts and fresh registration. {user_info}")


@pytest.fixture(scope="session")
def admin_token(api_url: str, app_health) -> str:
    return _ensure_admin(api_url)


@pytest.fixture
def auth_header(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def clean_settings(api_url: str, auth_header: dict):
    yield
    resp = requests.get(f"{api_url}/settings/public", timeout=5)
    site_name = resp.json().get("site_name", "")
    requests.put(f"{api_url}/settings", json={
        "site_name": site_name,
        "dingtalk_webhook": "",
        "dingtalk_secret": "",
    }, headers=auth_header)
