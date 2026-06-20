import redis.asyncio as aioredis

from app.core.config import settings

_redis_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return a shared async Redis client (connection pooled)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=100,
        )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
