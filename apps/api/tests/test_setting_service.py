import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from fastapi import FastAPI

from routers.settings import router
from app.core.auth import get_current_user, AuthenticatedUser
from models.setting import DEFAULTS


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
    user_id="test-user", username="testuser"
)
client = TestClient(app)

public_app = FastAPI()
public_app.include_router(router)
public_client = TestClient(public_app)


def _mock_redis(return_none=False):
    m = AsyncMock()
    if return_none:
        m.hgetall.return_value = {}
        m.hget.return_value = None
    return m


# ---------------------------------------------------------------------------
#  Service unit tests
# ---------------------------------------------------------------------------

class TestSettingServiceGetSetting:

    @pytest.mark.asyncio
    async def test_redis_hit_returns_cached_value(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hget.return_value = "自定义名称"
        with patch("services.setting_service.get_redis", return_value=mock_r):
            val = await SettingService.get_setting("site_name")
        assert val == "自定义名称"
        mock_r.hget.assert_awaited_once_with("system:settings", "site_name")

    @pytest.mark.asyncio
    async def test_redis_miss_falls_back_to_db(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hget.return_value = None
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {"_id": "global", "site_name": "库里的值"}
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            val = await SettingService.get_setting("site_name")
        assert val == "库里的值"

    @pytest.mark.asyncio
    async def test_redis_miss_db_empty_returns_default(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hget.return_value = None
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = None
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            val = await SettingService.get_setting("site_name")
        assert val == DEFAULTS["site_name"]

    @pytest.mark.asyncio
    async def test_redis_unavailable_uses_db(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {"_id": "global", "site_name": "db_val"}
        with patch("services.setting_service.get_redis", return_value=None), \
             patch("services.setting_service.get_db", return_value=mock_db):
            val = await SettingService.get_setting("site_name")
        assert val == "db_val"


class TestSettingServiceSetSetting:

    @pytest.mark.asyncio
    async def test_writes_to_db_and_redis(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            result = await SettingService.set_setting("site_name", "新名称")
        assert result is True
        mock_db.system_settings.update_one.assert_called_once()
        mock_r.hset.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graceful_when_redis_unavailable(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=None):
            result = await SettingService.set_setting("site_name", "新名称")
        assert result is True

    @pytest.mark.asyncio
    async def test_records_updated_at(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            await SettingService.set_setting("site_name", "val")
        call_args = mock_db.system_settings.update_one.call_args
        assert call_args is not None
        set_data = call_args[0][1]["$set"]
        assert "updated_at" in set_data

    @pytest.mark.asyncio
    async def test_persists_int_value(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            await SettingService.set_setting("session_expire_minutes", 60)
        call_args = mock_db.system_settings.update_one.call_args
        set_data = call_args[0][1]["$set"]
        assert set_data["session_expire_minutes"] == 60


class TestSettingServiceGetAllSettings:

    @pytest.mark.asyncio
    async def test_returns_all_defaults_when_empty(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {}
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = None
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            result = await SettingService.get_all_settings()
        assert result["site_name"] == DEFAULTS["site_name"]
        assert result["session_expire_minutes"] == 30
        assert result["llm_api_key"] == ""

    @pytest.mark.asyncio
    async def test_merges_db_values_with_defaults(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {}
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {"_id": "global", "site_name": "生产系统"}
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            result = await SettingService.get_all_settings()
        assert result["site_name"] == "生产系统"
        assert result["site_status"] == "open"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {"site_name": "缓存名称", "site_status": "closed"}
        mock_db = MagicMock()
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            result = await SettingService.get_all_settings()
        assert result["site_name"] == "缓存名称"
        assert result["site_status"] == "closed"
        mock_db.system_settings.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_preserves_type(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {
            "session_expire_minutes": "45",
            "llm_batch_size": "200",
            "site_name": "系统",
        }
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=MagicMock()):
            result = await SettingService.get_all_settings()
        assert result["session_expire_minutes"] == 45
        assert result["llm_batch_size"] == 200

    @pytest.mark.asyncio
    async def test_cache_hit_sets_expiry(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {}
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = None
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            await SettingService.get_all_settings()
        mock_r.expire.assert_awaited_once_with("system:settings", 3600)

    @pytest.mark.asyncio
    async def test_cache_populated_after_db_read(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {}
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {"_id": "global", "site_name": "db名称"}
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            await SettingService.get_all_settings()
        mock_r.hset.assert_awaited_once()
        call_kwargs = mock_r.hset.call_args.kwargs
        mapping = call_kwargs.get("mapping")
        assert mapping["site_name"] == "db名称"


class TestSettingServiceBatchUpdate:

    @pytest.mark.asyncio
    async def test_updates_multiple_fields(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        updates = {"site_name": "新系统", "site_status": "closed"}
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            result = await SettingService.batch_update(updates)
        assert result is True
        call_args = mock_db.system_settings.update_one.call_args
        set_data = call_args[0][1]["$set"]
        assert set_data["site_name"] == "新系统"
        assert set_data["site_status"] == "closed"

    @pytest.mark.asyncio
    async def test_ignores_unknown_keys(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            result = await SettingService.batch_update({"unknown_key": "val"})
        assert result is False
        mock_db.system_settings.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_updated_at(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            await SettingService.batch_update({"site_name": "x"})
        call_args = mock_db.system_settings.update_one.call_args
        set_data = call_args[0][1]["$set"]
        assert "updated_at" in set_data

    @pytest.mark.asyncio
    async def test_refreshes_redis_cache(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            await SettingService.batch_update({"site_name": "x"})
        mock_r.hset.assert_awaited_once()


class TestSettingServiceGetPublicSettings:

    @pytest.mark.asyncio
    async def test_only_public_fields_returned(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {
            "site_name": "系统",
            "llm_api_key": "sk-secret",
            "dingtalk_secret": "secret",
            "llm_model": "gpt-5",
        }
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=MagicMock()):
            result = await SettingService.get_public_settings()
        assert "llm_api_key" not in result
        assert "dingtalk_secret" not in result
        assert "llm_model" not in result
        assert result["site_name"] == "系统"

    @pytest.mark.asyncio
    async def test_returns_defaults_when_empty(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {}
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = None
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            result = await SettingService.get_public_settings()
        assert result["site_name"] == DEFAULTS["site_name"]
        assert result["site_status"] == "open"

    @pytest.mark.asyncio
    async def test_returns_db_override(self):
        from services.setting_service import SettingService
        mock_r = AsyncMock()
        mock_r.hgetall.return_value = {}
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {"_id": "global", "site_name": "自定义"}
        with patch("services.setting_service.get_redis", return_value=mock_r), \
             patch("services.setting_service.get_db", return_value=mock_db):
            result = await SettingService.get_public_settings()
        assert result["site_name"] == "自定义"


class TestSettingServiceRefreshCache:

    @pytest.mark.asyncio
    async def test_deletes_and_reloads_cache(self):
        from services.setting_service import SettingService
        mock_db = MagicMock()
        mock_db.system_settings.find_one.return_value = {
            "_id": "global", "site_name": "refresh_val",
        }
        mock_r = AsyncMock()
        with patch("services.setting_service.get_db", return_value=mock_db), \
             patch("services.setting_service.get_redis", return_value=mock_r):
            result = await SettingService.refresh_cache()
        assert result is True
        mock_r.delete.assert_awaited_once_with("system:settings")
        mock_r.hset.assert_awaited_once()
        mock_r.expire.assert_awaited_once_with("system:settings", 3600)

    @pytest.mark.asyncio
    async def test_returns_false_when_redis_unavailable(self):
        from services.setting_service import SettingService
        with patch("services.setting_service.get_redis", return_value=None):
            result = await SettingService.refresh_cache()
        assert result is False


# ---------------------------------------------------------------------------
#  Router integration tests (mock service layer)
# ---------------------------------------------------------------------------

class TestRouterGetPublicSettings:

    def test_returns_public_settings(self):
        mock_svc = AsyncMock()
        mock_svc.return_value = {"site_name": "系统"}
        with patch("routers.settings.SettingService.get_public_settings", mock_svc):
            response = public_client.get("/settings/public")
        assert response.status_code == 200
        assert response.json()["site_name"] == "系统"

    def test_no_auth_required(self):
        mock_svc = AsyncMock()
        mock_svc.return_value = {"site_name": "系统"}
        with patch("routers.settings.SettingService.get_public_settings", mock_svc):
            response = client.get("/settings/public")
        assert response.status_code == 200

    def test_returns_500_on_service_error(self):
        error_client = TestClient(app, raise_server_exceptions=False)
        mock_svc = AsyncMock()
        mock_svc.side_effect = Exception("Service error")
        with patch("routers.settings.SettingService.get_public_settings", mock_svc):
            response = error_client.get("/settings/public")
        assert response.status_code == 500


class TestRouterGetSettings:

    def test_returns_all_settings(self):
        mock_svc = AsyncMock()
        mock_svc.return_value = {"site_name": "test", **{k: v for k, v in DEFAULTS.items() if k != "site_name"}}
        with patch("routers.settings.SettingService.get_all_settings", mock_svc):
            response = client.get("/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["site_name"] == "test"

    def test_returns_401_without_auth(self):
        response = public_client.get("/settings")
        assert response.status_code in (401, 403)

    def test_returns_500_on_service_error(self):
        error_client = TestClient(app, raise_server_exceptions=False)
        mock_svc = AsyncMock()
        mock_svc.side_effect = Exception("Error")
        with patch("routers.settings.SettingService.get_all_settings", mock_svc):
            response = error_client.get("/settings")
        assert response.status_code == 500


class TestRouterUpdateSettings:

    def test_admin_can_update(self):
        mock_svc = AsyncMock()
        mock_svc.return_value = True
        with patch("routers.settings.SettingService.batch_update", mock_svc), \
             patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "admin"}]):
            response = client.put("/settings", json={"site_name": "新名称"})
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "设置已保存"
        assert data["site_name"] == "新名称"

    def test_super_admin_can_update(self):
        mock_svc = AsyncMock()
        mock_svc.return_value = True
        with patch("routers.settings.SettingService.batch_update", mock_svc), \
             patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "super_admin"}]):
            response = client.put("/settings", json={"site_name": "test"})
        assert response.status_code == 200

    def test_non_admin_gets_403(self):
        with patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "user"}]):
            response = client.put("/settings", json={"site_name": "新名称"})
        assert response.status_code == 403

    def test_unknown_key_returns_422(self):
        with patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "admin"}]):
            response = client.put("/settings", json={"unknown_field": "val"})
        assert response.status_code == 422

    def test_none_fields_are_excluded(self):
        mock_svc = AsyncMock()
        with patch("routers.settings.SettingService.batch_update", mock_svc), \
             patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "admin"}]):
            response = client.put("/settings", json={
                "site_name": "名称",
                "site_description": None,
            })
        assert response.status_code == 200
        mock_svc.assert_awaited_once_with({"site_name": "名称"})

    def test_returns_500_on_service_error(self):
        error_client = TestClient(app, raise_server_exceptions=False)
        mock_svc = AsyncMock()
        mock_svc.side_effect = Exception("DB error")
        with patch("routers.settings.SettingService.batch_update", mock_svc), \
             patch("services.role_service.RoleService.get_user_roles",
                   return_value=[{"preset_key": "admin"}]):
            response = error_client.put("/settings", json={"site_name": "test"})
        assert response.status_code == 500


# ---------------------------------------------------------------------------
#  DEFAULTS integrity tests
# ---------------------------------------------------------------------------

class TestDEFAULTS:

    def test_all_defaults_keys_match_model(self):
        from models.setting import DEFAULTS
        expected_keys = {
            "site_name", "site_description", "site_logo", "site_favicon",
            "site_domain", "icp_beian", "icp_beian_url", "official_url",
            "frontend_url", "backend_url", "site_status", "close_tip",
            "timezone", "date_format", "time_format", "session_expire_minutes",
            "dingtalk_webhook", "dingtalk_secret", "llm_api_url", "llm_api_key",
            "llm_model", "llm_batch_size",
        }
        assert set(DEFAULTS.keys()) == expected_keys

    def test_critical_defaults(self):
        from models.setting import DEFAULTS
        assert DEFAULTS["site_name"] == "持仓管理系统"
        assert DEFAULTS["site_status"] == "open"
        assert DEFAULTS["timezone"] == "Asia/Shanghai"
        assert DEFAULTS["session_expire_minutes"] == 30

    def test_secret_defaults_are_empty(self):
        from models.setting import DEFAULTS
        assert DEFAULTS["dingtalk_webhook"] == ""
        assert DEFAULTS["dingtalk_secret"] == ""
        assert DEFAULTS["llm_api_key"] == ""
