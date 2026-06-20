"""任务进度发布/订阅。

Worker(同步)向 Redis 频道发布进度,API 的 WebSocket(异步)订阅并转发给前端。
频道按 task public_id 划分。
"""

from __future__ import annotations

import json
from typing import Any

import redis as sync_redis

from app.core.config import settings
from app.core.redis import get_redis

CHANNEL = "task:progress:{public_id}"
SNAPSHOT_KEY = "task:snapshot:{public_id}"

_sync_client: sync_redis.Redis | None = None


def _sync() -> sync_redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = sync_redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_client


def publish_progress(public_id: str, payload: dict[str, Any]) -> None:
    """供 Worker 调用(同步)。"""
    r = _sync()
    data = json.dumps(payload, ensure_ascii=False)
    # 存最新快照,供 WS 刚连接时立即下发
    r.set(SNAPSHOT_KEY.format(public_id=public_id), data, ex=3600)
    r.publish(CHANNEL.format(public_id=public_id), data)


async def get_snapshot(public_id: str) -> dict[str, Any] | None:
    r = get_redis()
    data = await r.get(SNAPSHOT_KEY.format(public_id=public_id))
    return json.loads(data) if data else None
