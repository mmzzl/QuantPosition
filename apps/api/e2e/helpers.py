import requests


def ensure_admin_user(api_url: str) -> bool:
    resp = requests.post(f"{api_url}/auth/register", json={
        "username": "admin",
        "password": "admin123",
        "email": "admin@example.com",
    })
    if resp.status_code == 201:
        return True
    if resp.status_code == 400 and "already exists" in resp.text:
        return False
    raise RuntimeError(f"Unexpected response from register: {resp.status_code} {resp.text}")
