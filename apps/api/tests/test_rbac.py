import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from fastapi import FastAPI
import pytest

from app.core.auth import (
    get_current_user, get_current_active_user, AuthenticatedUser,
    get_password_hash, create_access_token,
)

VALID_OID = "507f1f77bcf86cd799439011"
VALID_OID2 = "507f1f77bcf86cd799439012"
VALID_OID3 = "507f1f77bcf86cd799439013"
NOW = datetime.now()


def _make_role(rid, name, perms=None, parents=None, locked=False, role_type="custom", preset_key=None):
    return {
        "_id": rid, "name": name or rid,
        "permission_ids": perms or [],
        "parent_roles": parents or [],
        "locked": locked,
        "role_type": role_type,
        "preset_key": preset_key,
        "description": "",
        "created_at": NOW, "updated_at": NOW,
    }


def _make_perm(pid, name, resource="holdings", action="view", menu_path=None, menu_label=None):
    return {
        "_id": pid, "name": name,
        "resource": resource, "action": action,
        "menu_path": menu_path, "menu_label": menu_label,
        "created_at": NOW,
    }


# ============================================================
# Scenario 1 (normal): Full auth + RBAC + Menu flow
# ============================================================

class TestFullAuthFlow:

    def test_register_login_get_users_effective_permissions_menu(self):
        from routers.auth import router as auth_router
        from routers.users import router as users_router
        from routers.roles import router as roles_router
        from routers.menu import router as menu_router
        from services.role_service import RoleService

        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(users_router)
        app.include_router(roles_router)
        app.include_router(menu_router)
        client = TestClient(app)

        role_id = VALID_OID
        perm_id = VALID_OID2
        user_id = VALID_OID3
        hashed_pw = get_password_hash("testpass123")
        mock_db = MagicMock()

        mock_db.users.find_one.side_effect = [
            None,
            {"_id": user_id, "username": "newuser", "password_hash": hashed_pw,
             "is_active": True, "login_failed_attempts": 0, "locked_until": None,
             "created_at": NOW, "updated_at": NOW},
        ]
        mock_db.users.insert_one.return_value = MagicMock(inserted_id=user_id)
        mock_db.roles.find_one.return_value = _make_role(role_id, "普通管理员", preset_key="normal_admin", role_type="preset")
        mock_db.roles.find.return_value = []
        mock_db.roles.insert_one.return_value = MagicMock(inserted_id=role_id)
        mock_db.user_roles.find_one.return_value = None
        mock_db.system_settings.find_one.return_value = None
        mock_db.permissions.find.return_value = []
        mock_db.permissions.find_one.return_value = _make_perm(perm_id, "holdings:view")

        mock_db.users.update_one = MagicMock()

        with patch("routers.auth.get_db", return_value=mock_db):
            with patch("services.role_service.get_db", return_value=mock_db):
                with patch("services.user_service.get_db", return_value=mock_db):
                    resp = client.post("/auth/register", json={
                        "username": "newuser", "password": "testpass123",
                    })

        assert resp.status_code == 201
        assert resp.json()["username"] == "newuser"

        with patch("routers.auth.get_db", return_value=mock_db):
            with patch("services.role_service.get_db", return_value=mock_db):
                resp = client.post("/auth/login", json={
                    "username": "newuser", "password": "testpass123",
                })

        assert resp.status_code == 200
        token_data = resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

        token = token_data["access_token"]

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=user_id, username="newuser"
        )

        with patch("services.user_service.get_db", return_value=mock_db):
            resp = client.get("/users",
                              headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200

        with patch.object(RoleService, 'get_effective_permissions', return_value=[perm_id]):
            with patch("database.get_db", return_value=mock_db):
                resp = client.get(f"/roles/{role_id}/effective-permissions",
                                 headers={"Authorization": f"Bearer {token}"})

            assert resp.status_code == 200
            data = resp.json()
            assert data["role_id"] == role_id
            assert "effective_permissions" in data


# ============================================================
# Scenario 2 (exception): Error handling
# ============================================================

class TestExceptions:

    def test_wrong_password_returns_401(self):
        from routers.auth import router as auth_router

        app = FastAPI()
        app.include_router(auth_router)
        client = TestClient(app)

        hashed = get_password_hash("correctpass")
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "user",
            "password_hash": hashed, "is_active": True,
            "login_failed_attempts": 0, "locked_until": None,
        }
        mock_db.users.update_one = MagicMock()

        with patch("routers.auth.get_db", return_value=mock_db):
            resp = client.post("/auth/login", json={
                "username": "user", "password": "wrongpass",
            })

        assert resp.status_code == 401

    def test_circular_inheritance_detected(self):
        from services.role_service import RoleService

        role_map = {
            "r1": _make_role("r1", "Role1", parents=["r2"]),
            "r2": _make_role("r2", "Role2", parents=["r1"]),
        }

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            result = RoleService.detect_inheritance_cycle("r1", "r2")

        assert result is True

    def test_preset_role_deletion_returns_400(self):
        from routers.roles import router as roles_router

        app = FastAPI()
        app.include_router(roles_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )
        client = TestClient(app)

        mock_db = MagicMock()
        mock_db.roles.find_one.return_value = _make_role(
            VALID_OID, "预设角色", role_type="preset", preset_key="normal_admin"
        )

        with patch("services.role_service.get_db", return_value=mock_db):
            with patch("services.role_service.RoleService.get_user_roles",
                       return_value=[{"preset_key": "super_admin"}]):
                resp = client.delete(f"/roles/{VALID_OID}")

        assert resp.status_code == 400

    def test_locked_role_not_modifiable(self):
        from services.role_service import RoleService
        from models.role import RoleUpdate

        mock_db = MagicMock()
        mock_db.roles.find_one.return_value = _make_role(
            VALID_OID, "LockedRole", locked=True, role_type="preset",
            preset_key="system_admin"
        )

        with patch("services.role_service.get_db", return_value=mock_db):
            with pytest.raises(ValueError, match="locked"):
                RoleService.update_role(VALID_OID, RoleUpdate(name="NewName"))


# ============================================================
# Scenario 3 (boundary): Inheritance depth & lockout
# ============================================================

class TestBoundaryConditions:

    def test_inheritance_depth_5_truncates(self):
        from services.role_service import RoleService

        role_map = {}
        for i in range(7):
            role_map[f"r{i}"] = _make_role(f"r{i}", f"Level{i}",
                                            perms=[f"p{i}"],
                                            parents=[f"r{i+1}"] if i < 6 else [])

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            perms = RoleService.get_effective_permissions("r0")

        assert len(perms) <= 6

    def test_login_fails_5_times_locks_account(self):
        from routers.auth import router as auth_router

        app = FastAPI()
        app.include_router(auth_router)
        client = TestClient(app)

        hashed = get_password_hash("correct")
        mock_db = MagicMock()

        class StatefulMock:
            def __init__(self):
                self.attempts = 0
                self.locked_until = None

            def find_user(self, query, *args, **kwargs):
                if self.locked_until:
                    return {"_id": VALID_OID, "username": "target", "password_hash": hashed,
                            "is_active": True, "login_failed_attempts": self.attempts,
                            "locked_until": self.locked_until}
                return {"_id": VALID_OID, "username": "target", "password_hash": hashed,
                        "is_active": True, "login_failed_attempts": self.attempts,
                        "locked_until": None}

            def update_user(self, query, update, **kwargs):
                inc = update.get("$inc", {})
                inc_attempts = inc.get("login_failed_attempts", 0)
                self.attempts += inc_attempts
                set_data = update.get("$set", {})
                if "locked_until" in set_data:
                    self.locked_until = set_data["locked_until"]
                if "login_failed_attempts" in set_data and set_data["login_failed_attempts"] == 0:
                    self.attempts = 0
                    self.locked_until = None
                return MagicMock(modified_count=1)

        state = StatefulMock()
        mock_db.users.find_one = state.find_user
        mock_db.users.update_one = state.update_user
        mock_db.system_settings.find_one.return_value = None

        for attempt in range(5):
            with patch("routers.auth.get_db", return_value=mock_db):
                resp = client.post("/auth/login", json={
                    "username": "target", "password": "wrong",
                })
            assert resp.status_code == 401

        assert state.locked_until is not None, "Account should be locked after 5 attempts"

        with patch("routers.auth.get_db", return_value=mock_db):
            resp = client.post("/auth/login", json={
                "username": "target", "password": "wrong",
            })
        assert resp.status_code == 423

    def test_successful_login_resets_failed_attempts(self):
        from routers.auth import router as auth_router

        app = FastAPI()
        app.include_router(auth_router)
        client = TestClient(app)

        hashed = get_password_hash("correct")
        mock_db = MagicMock()
        mock_db.users.find_one.return_value = {
            "_id": VALID_OID, "username": "gooduser", "password_hash": hashed,
            "is_active": True, "login_failed_attempts": 3, "locked_until": None,
        }
        mock_db.system_settings.find_one.return_value = None
        mock_db.user_roles.find_one.return_value = None

        update_set_data = {}

        def fake_update_one(query, update, **kwargs):
            nonlocal update_set_data
            update_set_data = update.get("$set", {})

        mock_db.users.update_one = fake_update_one

        with patch("routers.auth.get_db", return_value=mock_db):
            resp = client.post("/auth/login", json={
                "username": "gooduser", "password": "correct",
            })

        assert resp.status_code == 200
        assert update_set_data.get("login_failed_attempts") == 0
        assert update_set_data.get("locked_until") is None


# ============================================================
# Menu permission tests
# ============================================================

class TestMenuPermissions:

    def test_menu_returns_structure(self):
        from routers.menu import router as menu_router
        from services.role_service import RoleService

        app = FastAPI()
        app.include_router(menu_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )
        client = TestClient(app)

        with patch.object(RoleService, 'get_user_roles',
                          return_value=[{"preset_key": "super_admin"}]):
            resp = client.get("/menu")

        assert resp.status_code == 200
        data = resp.json()
        assert "menu" in data
        assert "authority_prms" in data

    def test_regular_user_gets_limited_menu(self):
        from routers.menu import router as menu_router
        from services.role_service import RoleService

        app = FastAPI()
        app.include_router(menu_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="user"
        )
        client = TestClient(app)

        with patch.object(RoleService, 'get_user_roles',
                          return_value=[{"preset_key": None, "name": "custom_user", "role_type": "custom"}]):
            resp = client.get("/menu")

        assert resp.status_code == 200
        data = resp.json()
        assert "menu" in data
        menu_titles = [m.get("title", "") for m in data["menu"]]
        assert "系统管理" not in menu_titles


# ============================================================
# User-role assignment tests
# ============================================================

class TestUserRoleAssignment:

    def test_add_user_to_role_and_get_my_roles(self):
        from routers.roles import router as roles_router
        from routers.users import router as users_router

        app = FastAPI()
        app.include_router(roles_router)
        app.include_router(users_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )
        client = TestClient(app)

        mock_db = MagicMock()
        mock_db.user_roles.find_one.return_value = None
        mock_db.user_roles.find.return_value = [
            {"user_id": VALID_OID, "role_id": VALID_OID2}
        ]
        mock_db.roles.find_one = MagicMock()
        mock_db.roles.find_one.return_value = _make_role(
            VALID_OID2, "TestRole", preset_key="custom"
        )
        mock_db.roles.find.return_value = [
            _make_role(VALID_OID2, "TestRole", preset_key="custom")
        ]

        with patch("services.role_service.get_db", return_value=mock_db):
            with patch("services.role_service.RoleService.get_user_roles",
                       return_value=[{"preset_key": "super_admin"}]):
                resp = client.post(f"/roles/{VALID_OID2}/users/{VALID_OID3}")

        assert resp.status_code == 200

        with patch("services.role_service.RoleService.get_user_roles",
                   return_value=[_make_role(VALID_OID2, "TestRole", preset_key="custom")]):
            resp = client.get("/users/me/roles")

        assert resp.status_code == 200
        roles = resp.json()
        assert len(roles) >= 1


class TestPermissionManagement:

    def test_create_and_list_permissions(self):
        from routers.permissions import router as perm_router

        app = FastAPI()
        app.include_router(perm_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )
        client = TestClient(app)

        mock_db = MagicMock()
        mock_db.permissions.find_one.return_value = None
        mock_db.permissions.insert_one.return_value = MagicMock(inserted_id=VALID_OID)
        mock_db.permissions.find.return_value = [
            {"_id": VALID_OID, "name": "test:action", "resource": "test",
             "action": "action", "created_at": NOW},
        ]

        with patch("routers.permissions.get_db", return_value=mock_db):
            resp = client.post("/permissions", json={
                "name": "test:action", "resource": "test", "action": "action",
            })

        assert resp.status_code == 200

        with patch("routers.permissions.get_db", return_value=mock_db):
            resp = client.get("/permissions")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["items"][0]["name"] == "test:action"

    def test_delete_permission(self):
        from routers.permissions import router as perm_router

        app = FastAPI()
        app.include_router(perm_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )
        client = TestClient(app)

        mock_db = MagicMock()
        mock_db.permissions.delete_one.return_value = MagicMock(deleted_count=1)

        with patch("routers.permissions.get_db", return_value=mock_db):
            resp = client.delete(f"/permissions/{VALID_OID}")

        assert resp.status_code == 200
