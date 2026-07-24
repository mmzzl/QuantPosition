import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_pool = None


def init_redis_pool(host: str = "localhost", port: int = 6379, db: int = 0, max_connections: int = 10) -> None:
    global _redis_pool
    try:
        import redis.asyncio as aioredis
        _redis_pool = aioredis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            max_connections=max_connections,
            decode_responses=True,
        )
        logger.info("Redis connection pool initialized", extra={"host": host, "port": port})
    except ImportError:
        logger.warning("redis.asyncio not available, Redis support disabled")


async def get_redis() -> "Optional[aioredis.Redis]":
    if _redis_pool is None:
        return None
    import redis.asyncio as aioredis
    return aioredis.Redis(connection_pool=_redis_pool)


async def ping_redis() -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        return await r.ping()
    except Exception:
        return False


def close_redis_pool():
    global _redis_pool
    if _redis_pool:
        _redis_pool.disconnect()
        _redis_pool = None
