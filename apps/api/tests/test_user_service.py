import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import pytest

from routers.users import router
from app.core.auth import get_current_user, get_current_active_user, AuthenticatedUser, get_password_hash
from datetime import datetime

app = FastAPI()
app.include_router(router)

VALID_OID = "507f1f77bcf86cd799439011"
OTHER_OID = "507f1f77bcf86cd799439012"
NOW = datetime.now()

test_user = AuthenticatedUser(user_id=VALID_OID, username="admin")


class TestGetUsers:

    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: test_user

    def test_returns_user_list(self):
        mock_db = MagicMock()
        mock_db.users.find.return_value.skip.return_value.limit.return_value = [
            {"_id": VALID_OID, "username": "user1", "email": "u1@test.com",
             "is_active": True, "created_at": NOW, "updated_at": NOW},
        ]

        with patch("services.user_service.get_db", return_value=mock_db):
            response = TestClient(app).get("/users")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["username"] == "user1"

    def test_supports_pagination(self):
        mock_db = MagicMock()
        mock_db.users.find.return_value.skip.return_value.limit.return_value = []

        with patch("services.user_service.get_db", return_value=mock_db) as mock_get:
            TestClient(app).get("/users?skip=10&limit=20")

        mock_get.return_value.users.find.assert_called_once()
        mock_get.return_value.users.find.return_value.skip.assert_called_with(10)
        mock_get.return_value.users.find.return_value.skip.return_value.limit.assert_called_with(20)

    def test_returns_401_without_auth(self):
        app.dependency_overrides[get_current_user] = get_current_user
        public_client = TestClient(app)
        response = public_client.get("/users")
        assert response.status_code == 401


class TestCreateUser:

    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: test_user

    def test_creates_user_successfully(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = None
        mock_db.users.insert_one.return_value = MagicMock(inserted_id=VALID_OID)

        with patch("services.user_service.get_db", return_value=mock_db):
            response = TestClient(app).post("/users", json={
                "username": "newuser",
                "password": "pass123",
                "email": "new@test.com",
            })

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"

    def test_duplicate_username_returns_400(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {"_id": VALID_OID, "username": "existing"}

        with patch("services.user_service.get_db", return_value=mock_db):
            response = TestClient(app).post("/users", json={
                "username": "existing",
                "password": "pass123",
            })

        assert response.status_code == 400


class TestDeleteUser:

    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: test_user

    def test_delete_normal_user_returns_204(self):
        mock_db = MagicMock()
        mock_db.users.find_one.side_effect = [
            {"_id": OTHER_OID, "username": "normal_user", "is_active": True},
        ]
        mock_db.users.delete_one.return_value = MagicMock(deleted_count=1)

        with patch("routers.users.get_db", return_value=mock_db):
            with patch("services.user_service.get_db", return_value=mock_db):
                response = TestClient(app).delete(f"/users/{OTHER_OID}")

        assert response.status_code == 204

    def test_delete_admin_user_returns_400(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "admin", "is_active": True,
        }

        with patch("routers.users.get_db", return_value=mock_db):
            response = TestClient(app).delete(f"/users/{VALID_OID}")

        assert response.status_code == 400

    def test_delete_nonexistent_user_returns_404(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = None

        with patch("routers.users.get_db", return_value=mock_db):
            response = TestClient(app).delete(f"/users/{OTHER_OID}")

        assert response.status_code == 404


class TestChangePassword:

    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: test_user

    def test_own_password_change_succeeds(self):
        old_hash = get_password_hash("oldpass")
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "admin",
            "password_hash": old_hash, "is_active": True,
        }

        with patch("routers.users.get_db", return_value=mock_db):
            response = TestClient(app).put(f"/users/{VALID_OID}/password", json={
                "old_password": "oldpass",
                "new_password": "newpass123",
            })

        assert response.status_code == 200
        assert "Password changed" in response.text

    def test_wrong_old_password_returns_401(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "admin",
            "password_hash": get_password_hash("correct"),
            "is_active": True,
        }

        with patch("routers.users.get_db", return_value=mock_db):
            response = TestClient(app).put(f"/users/{VALID_OID}/password", json={
                "old_password": "wrong",
                "new_password": "newpass",
            })

        assert response.status_code == 401

    def test_change_other_user_password_needs_admin(self):
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": OTHER_OID, "username": "other",
            "password_hash": get_password_hash("pass"),
            "is_active": True,
        }

        with patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "normal_admin"}]):
            response = TestClient(app).put(f"/users/{OTHER_OID}/password", json={
                "old_password": "pass",
                "new_password": "newpass",
            })

        assert response.status_code == 403
