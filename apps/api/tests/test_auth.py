import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from datetime import timedelta, datetime
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from routers.auth import router
from app.core.auth import (
    verify_password, get_password_hash, create_access_token,
    decode_access_token, get_current_user, AuthenticatedUser,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestPasswordHashing:

    def test_hash_and_verify_match(self):
        password = "testpass123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_differs_each_call(self):
        h1 = get_password_hash("same")
        h2 = get_password_hash("same")
        assert h1 != h2


class TestJWTTokens:

    def test_create_and_decode(self):
        token = create_access_token({"sub": "testuser", "user_id": "123"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["username"] == "testuser"
        assert payload["user_id"] == "123"

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None

    def test_decode_expired_token(self):
        token = create_access_token(
            {"sub": "testuser", "user_id": "123"},
            expires_delta=timedelta(seconds=-1),
        )
        assert decode_access_token(token) is None

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "u", "user_id": "1"})
        from jose import jwt
        payload = jwt.get_unverified_claims(token)
        assert "exp" in payload


class TestRegister:

    def test_successful_registration(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = None
        mock_db.users.insert_one.return_value = MagicMock(inserted_id="new-id")
        mock_db.roles.find_one.return_value = {"_id": "role-id", "preset_key": "normal_admin"}

        with patch("routers.auth.get_db", return_value=mock_db):
            response = client.post("/auth/register", json={
                "username": "newuser",
                "password": "pass123",
                "email": "new@test.com",
            })

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@test.com"

    def test_duplicate_username_returns_400(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {"_id": "existing", "username": "existing"}

        with patch("routers.auth.get_db", return_value=mock_db):
            response = client.post("/auth/register", json={
                "username": "existing",
                "password": "pass123",
            })

        assert response.status_code == 400
        assert "already exists" in response.text

    def test_registration_missing_password_returns_422(self):
        response = client.post("/auth/register", json={"username": "test"})
        assert response.status_code == 422

    def test_registration_empty_body_returns_422(self):
        response = client.post("/auth/register", json={})
        assert response.status_code == 422

    def test_registration_db_error_returns_500(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = None
        mock_db.users.insert_one.side_effect = Exception("DB error")

        error_client = TestClient(app, raise_server_exceptions=False)
        with patch("routers.auth.get_db", return_value=mock_db):
            response = error_client.post("/auth/register", json={
                "username": "newuser",
                "password": "pass123",
            })

        assert response.status_code == 500

    def test_default_role_assigned(self):
        mock_db = MagicMock()
        mock_db.users.find_one.side_effect = [None, None, None]
        mock_db.users.insert_one.return_value = MagicMock(inserted_id="new-id")
        mock_db.roles.find_one.return_value = {"_id": "role-id", "preset_key": "normal_admin"}

        with patch("routers.auth.get_db", return_value=mock_db):
            client.post("/auth/register", json={
                "username": "user1",
                "password": "pass123",
            })

        mock_db.user_roles.insert_one.assert_called_once()


class TestLogin:

    def test_successful_login_returns_token(self):
        hashed = get_password_hash("pass123")
        role_objectid = "507f1f77bcf86cd799439011"
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": "user-id", "username": "testuser",
            "password_hash": hashed, "is_active": True,
        }
        mock_db.system_settings.find_one.return_value = None
        mock_db.user_roles.find_one.return_value = {"role_id": role_objectid}
        mock_db.roles.find_one.return_value = {"preset_key": "super_admin"}

        with patch("routers.auth.get_db", return_value=mock_db):
            response = client.post("/auth/login", json={
                "username": "testuser",
                "password": "pass123",
            })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "super_admin"

    def test_login_wrong_password_returns_401(self):
        hashed = get_password_hash("correctpass")
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": "id", "username": "user",
            "password_hash": hashed, "is_active": True,
        }

        with patch("routers.auth.get_db", return_value=mock_db):
            response = client.post("/auth/login", json={
                "username": "user",
                "password": "wrongpass",
            })

        assert response.status_code == 401

    def test_login_nonexistent_user_returns_401(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = None

        with patch("routers.auth.get_db", return_value=mock_db):
            response = client.post("/auth/login", json={
                "username": "nobody",
                "password": "pass",
            })

        assert response.status_code == 401

    def test_login_disabled_user_returns_403(self):
        hashed = get_password_hash("pass")
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": "id", "username": "disabled",
            "password_hash": hashed, "is_active": False,
        }

        with patch("routers.auth.get_db", return_value=mock_db):
            response = client.post("/auth/login", json={
                "username": "disabled",
                "password": "pass",
            })

        assert response.status_code == 403

    def test_login_empty_body_returns_422(self):
        response = client.post("/auth/login", json={})
        assert response.status_code == 422


VALID_OID = "507f1f77bcf86cd799439011"


class TestGetCurrentUser:

    def test_valid_token_returns_user(self):
        token = create_access_token({"sub": "validuser", "user_id": VALID_OID})

        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "validuser", "is_active": True,
        }

        with patch("database.get_db", return_value=mock_db):
            import asyncio
            creds = MagicMock()
            creds.credentials = token
            result = asyncio.run(get_current_user(creds))
            assert result.user_id == VALID_OID
            assert result.username == "validuser"
            assert result.is_active is True

    def test_missing_token_returns_401(self):
        import asyncio
        with pytest.raises(Exception):
            asyncio.run(get_current_user(None))

    def test_invalid_token_returns_401(self):
        import asyncio
        creds = MagicMock()
        creds.credentials = "invalid.token.here"
        with pytest.raises(Exception):
            asyncio.run(get_current_user(creds))

    def test_disabled_user_returns_403(self):
        token = create_access_token({"sub": "disabled", "user_id": VALID_OID})

        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "disabled", "is_active": False,
        }

        with patch("database.get_db", return_value=mock_db):
            import asyncio
            creds = MagicMock()
            creds.credentials = token
            with pytest.raises(Exception) as exc:
                asyncio.run(get_current_user(creds))
            assert "disabled" in str(exc.value).lower() or exc.value.status_code == 403
