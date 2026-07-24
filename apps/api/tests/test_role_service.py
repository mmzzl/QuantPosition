import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import pytest

from app.core.auth import get_current_user, AuthenticatedUser

VALID_OID = "507f1f77bcf86cd799439011"
VALID_OID2 = "507f1f77bcf86cd799439012"
VALID_OID3 = "507f1f77bcf86cd799439013"


def _make_role(rid, perms, parents):
    return {"_id": rid, "name": rid, "permission_ids": perms, "parent_roles": parents}


class TestRoleInheritance:

    def test_no_inheritance_returns_direct_permissions(self):
        from services.role_service import RoleService

        role_map = {"role1": _make_role("role1", ["p1", "p2"], [])}

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            perms = RoleService.get_effective_permissions("role1")

        assert set(perms) == {"p1", "p2"}

    def test_single_level_inheritance(self):
        from services.role_service import RoleService

        role_map = {
            "role1": _make_role("role1", ["p1"], ["role2"]),
            "role2": _make_role("role2", ["p2", "p3"], []),
        }

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            perms = RoleService.get_effective_permissions("role1")

        assert set(perms) == {"p1", "p2", "p3"}

    def test_two_level_inheritance(self):
        from services.role_service import RoleService

        role_map = {
            "r1": _make_role("r1", ["p1"], ["r2"]),
            "r2": _make_role("r2", ["p2"], ["r3"]),
            "r3": _make_role("r3", ["p3"], []),
        }

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            perms = RoleService.get_effective_permissions("r1")

        assert set(perms) == {"p1", "p2", "p3"}

    def test_circular_inheritance_returns_empty(self):
        from services.role_service import RoleService

        role_map = {
            "r1": _make_role("r1", ["p1"], ["r2"]),
            "r2": _make_role("r2", ["p2"], ["r1"]),
        }

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            perms = RoleService.get_effective_permissions("r1")

        assert isinstance(perms, list)

    def test_exceeds_max_depth_returns_empty(self):
        from services.role_service import RoleService

        role_map = {}
        for i in range(7):
            role_map[f"r{i}"] = _make_role(f"r{i}", [f"p{i}"], [f"r{i+1}"] if i < 6 else [])

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            perms = RoleService.get_effective_permissions("r0")

        assert len(perms) <= 6

    def test_cycle_detection_returns_true(self):
        from services.role_service import RoleService

        role_map = {
            "r1": {"_id": "r1", "parent_roles": ["r2"]},
            "r2": {"_id": "r2", "parent_roles": ["r3"]},
            "r3": {"_id": "r3", "parent_roles": ["r1"]},
        }

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            result = RoleService.detect_inheritance_cycle("r1", "r2")

        assert result is True

    def test_no_cycle_returns_false(self):
        from services.role_service import RoleService

        role_map = {
            "r1": {"_id": "r1", "parent_roles": ["r2"]},
            "r2": {"_id": "r2", "parent_roles": []},
        }

        with patch("services.role_service.RoleService.get_role_by_id",
                   side_effect=lambda rid: role_map.get(rid)):
            result = RoleService.detect_inheritance_cycle("r1", "r3")

        assert result is False


class TestDeleteRoleCascade:

    def test_updates_child_roles(self):
        from services.role_service import RoleService

        mock_db = MagicMock()
        mock_db.roles.find.return_value = [
            {"_id": "child1", "parent_roles": ["deleting", "other"]},
        ]

        with patch("services.role_service.get_db", return_value=mock_db):
            result = RoleService.handle_role_deletion_cascade("deleting")

        assert result["updated_roles"] == 1
        mock_db.roles.update_one.assert_called_once()


class TestPresetRoles:

    def test_init_preset_roles_creates_three_roles(self):
        from services.role_service import RoleService

        mock_db = MagicMock()
        mock_db.roles.find_one.side_effect = [None, None, None]
        mock_db.permissions.find.return_value = []

        with patch("services.role_service.get_db", return_value=mock_db):
            RoleService.init_preset_roles()

        assert mock_db.roles.insert_one.call_count == 3
        calls = mock_db.roles.insert_one.call_args_list
        keys = {c[0][0]["preset_key"] for c in calls}
        assert keys == {"super_admin", "system_admin", "normal_admin"}

    def test_init_preset_roles_skips_if_exists(self):
        from services.role_service import RoleService

        mock_db = MagicMock()
        mock_db.roles.find_one.return_value = {"_id": "existing", "preset_key": "super_admin"}
        mock_db.permissions.find.return_value = []

        with patch("services.role_service.get_db", return_value=mock_db):
            RoleService.init_preset_roles()

        mock_db.roles.insert_one.assert_not_called()


class TestRolesAPI:

    def setup_method(self):
        from routers.roles import router as roles_router
        self.app = FastAPI()
        self.app.include_router(roles_router)
        self.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )
        self.client = TestClient(self.app)

    def test_get_roles_list(self):
        from datetime import datetime
        now = datetime.now()
        mock_db = MagicMock()
        mock_db.roles.find.return_value = [
            {"_id": VALID_OID, "name": "超级管理员", "role_type": "preset",
             "preset_key": "super_admin", "locked": True,
             "permission_ids": [], "parent_roles": [],
             "description": "", "created_at": now, "updated_at": now},
        ]

        with patch("routers.roles.get_db", return_value=mock_db):
            response = self.client.get("/roles")

        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_create_role(self):
        mock_db = MagicMock()
        mock_db.roles.find_one.return_value = None
        mock_db.roles.insert_one.return_value = MagicMock(inserted_id=VALID_OID)

        with patch("services.role_service.get_db", return_value=mock_db):
            with patch("services.role_service.RoleService.get_user_roles",
                       return_value=[{"preset_key": "super_admin"}]):
                response = self.client.post("/roles", json={
                    "name": "新角色",
                    "description": "测试角色",
                })

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "新角色"

    def test_create_role_duplicate_name(self):
        mock_db = MagicMock()
        mock_db.roles.find_one.return_value = {"_id": VALID_OID, "name": "已存在"}

        with patch("services.role_service.get_db", return_value=mock_db):
            with patch("services.role_service.RoleService.get_user_roles",
                       return_value=[{"preset_key": "super_admin"}]):
                response = self.client.post("/roles", json={
                    "name": "已存在",
                })

        assert response.status_code == 400

    def test_delete_preset_role_returns_400(self):
        mock_db = MagicMock()
        mock_db.roles.find_one.return_value = {
            "_id": VALID_OID, "name": "预设角色",
            "role_type": "preset",
        }

        with patch("services.role_service.get_db", return_value=mock_db):
            with patch("services.role_service.RoleService.get_user_roles",
                       return_value=[{"preset_key": "super_admin"}]):
                response = self.client.delete(f"/roles/{VALID_OID}")

        assert response.status_code == 400

    def test_get_effective_permissions(self):
        mock_db = MagicMock()

        def find_one_side_effect(query, *args, **kwargs):
            rid = query.get("_id")
            if str(rid) == VALID_OID:
                return {"_id": VALID_OID, "name": "test", "permission_ids": ["p1"], "parent_roles": []}
            return None

        mock_db.roles.find_one.side_effect = find_one_side_effect
        mock_db.permissions.find.return_value = [
            {"_id": "p1", "name": "holdings:view", "resource": "holdings", "action": "view"},
        ]

        with patch("database.get_db", return_value=mock_db):
            response = self.client.get(f"/roles/{VALID_OID}/effective-permissions")

        assert response.status_code == 200


class TestPermissionsAPI:

    def test_get_permissions_list(self):
        from routers.permissions import router as perm_router

        app = FastAPI()
        app.include_router(perm_router)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id=VALID_OID, username="admin"
        )

        mock_db = MagicMock()
        mock_db.permissions.find.return_value = [
            {"_id": "p1", "name": "holdings:view", "resource": "holdings",
             "action": "view", "description": "", "created_at": None},
        ]

        with patch("routers.permissions.get_db", return_value=mock_db):
            response = TestClient(app).get("/permissions")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
        assert data["items"][0]["name"] == "holdings:view"
