import logging
from datetime import datetime
from typing import Any

from database import get_db
from app.redis_client import get_redis
from models.setting import DEFAULTS, PUBLIC_FIELDS

logger = logging.getLogger(__name__)

CACHE_KEY = "system:settings"
CACHE_TTL = 3600


def _to_cache_value(key: str, value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _from_cache_value(key: str, raw: str) -> Any:
    default = DEFAULTS.get(key)
    if isinstance(default, bool):
        return raw.lower() in ("true", "1", "yes")
    if isinstance(default, int):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return raw
    if isinstance(default, float):
        try:
            return float(raw)
        except (ValueError, TypeError):
            return raw
    return raw


class SettingService:

    @staticmethod
    async def get_setting(key: str) -> Any:
        r = await get_redis()
        if r is not None:
            raw = await r.hget(CACHE_KEY, key)
            if raw is not None:
                logger.debug("Redis cache hit for setting: %s", key)
                return _from_cache_value(key, raw)
        db = get_db()
        doc = db.system_settings.find_one({"_id": "global"}) or {}
        return doc.get(key, DEFAULTS.get(key))

    @staticmethod
    async def set_setting(key: str, value: Any) -> bool:
        db = get_db()
        db.system_settings.update_one(
            {"_id": "global"},
            {"$set": {key: value, "updated_at": datetime.now()}},
            upsert=True,
        )
        r = await get_redis()
        if r is not None:
            await r.hset(CACHE_KEY, key, _to_cache_value(key, value))
        logger.info("Setting updated: %s = %s", key, value)
        return True

    @staticmethod
    async def get_all_settings() -> dict[str, Any]:
        r = await get_redis()
        if r is not None:
            cached = await r.hgetall(CACHE_KEY)
            if cached:
                logger.debug("Redis cache hit for all settings")
                result = dict(DEFAULTS)
                result.update({k: _from_cache_value(k, v) for k, v in cached.items()})
                return result
        db = get_db()
        doc = db.system_settings.find_one({"_id": "global"}) or {}
        result = dict(DEFAULTS)
        result.update((k, v) for k, v in doc.items() if k != "_id")
        if r is not None:
            mapping = {k: _to_cache_value(k, v) for k, v in result.items()}
            await r.hset(CACHE_KEY, mapping=mapping)
            await r.expire(CACHE_KEY, CACHE_TTL)
        return result

    @staticmethod
    async def batch_update(settings: dict[str, Any]) -> bool:
        valid = {k: v for k, v in settings.items() if k in DEFAULTS}
        if not valid:
            return False
        now = datetime.now()
        valid["updated_at"] = now
        db = get_db()
        db.system_settings.update_one(
            {"_id": "global"},
            {"$set": valid},
            upsert=True,
        )
        r = await get_redis()
        if r is not None:
            mapping = {k: _to_cache_value(k, v) for k, v in valid.items()}
            await r.hset(CACHE_KEY, mapping=mapping)
        logger.info("Batch updated settings: %s", list(valid.keys()))
        return True

    @staticmethod
    async def get_public_settings() -> dict[str, Any]:
        all_settings = await SettingService.get_all_settings()
        return {k: all_settings[k] for k in PUBLIC_FIELDS if k in all_settings}

    @staticmethod
    async def refresh_cache() -> bool:
        db = get_db()
        doc = db.system_settings.find_one({"_id": "global"}) or {}
        r = await get_redis()
        if r is None:
            return False
        await r.delete(CACHE_KEY)
        if doc:
            mapping = {k: _to_cache_value(k, v) for k, v in doc.items() if k != "_id"}
            await r.hset(CACHE_KEY, mapping=mapping)
            await r.expire(CACHE_KEY, CACHE_TTL)
        logger.info("Settings cache refreshed")
        return True
