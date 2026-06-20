"""基于 Redis 的额度与频控。

- 每日额度:key 按 user+type+date,自然日过期。
- 频控:每用户每分钟请求数,滑动窗口的简化版(固定 60s 窗口计数)。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.redis import get_redis
from app.models.enums import TaskType

DAILY_KEY = "quota:daily:{user_id}:{type}:{date}"
RATE_KEY = "ratelimit:{user_id}:{minute}"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


async def check_rate_limit(user_id: int) -> None:
    r = get_redis()
    minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    key = RATE_KEY.format(user_id=user_id, minute=minute)
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 60)
    if count > settings.USER_RATE_LIMIT_PER_MIN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁,请稍后再试",
        )


async def get_usage(user_id: int, task_type: TaskType) -> int:
    r = get_redis()
    key = DAILY_KEY.format(user_id=user_id, type=task_type.value, date=_today())
    val = await r.get(key)
    return int(val) if val else 0


async def consume_quota(user_id: int, task_type: TaskType, limit: int, amount: int = 1) -> None:
    """预扣额度;超限抛 429。"""
    r = get_redis()
    key = DAILY_KEY.format(user_id=user_id, type=task_type.value, date=_today())
    new_val = await r.incrby(key, amount)
    if new_val == amount:
        await r.expire(key, 86400)
    if new_val > limit:
        await r.decrby(key, amount)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日{('出图' if task_type == TaskType.image else '出视频')}额度已用完",
        )


async def refund_quota(user_id: int, task_type: TaskType, amount: int = 1) -> None:
    """任务失败时退还预扣额度。"""
    r = get_redis()
    key = DAILY_KEY.format(user_id=user_id, type=task_type.value, date=_today())
    await r.decrby(key, amount)
