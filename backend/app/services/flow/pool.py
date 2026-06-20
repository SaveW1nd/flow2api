"""账号池调度 + 并发闸门。

- 全局闸门:限制对 FLOW 的总并发(settings.FLOW_GLOBAL_CONCURRENCY)。
- 单账号闸门:限制每个账号并发(account.max_concurrency)。
- 选号策略:加权 + 当前在用数最少 + 成功率,跳过冷却/失效账号。

并发计数用 Redis 实现(跨进程/跨 worker 共享)。使用同步 redis 客户端,
因为账号选择发生在 Celery worker(同步上下文)。
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AccountStatus
from app.models.flow_account import FlowAccount
from app.services.flow.client import FlowCredential, FlowError

GLOBAL_KEY = "flow:concurrency:global"
ACCOUNT_KEY = "flow:concurrency:account:{account_id}"

_sync_redis: redis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis


class NoAccountAvailable(FlowError):
    def __init__(self, message: str = "暂无可用账号或并发已满"):
        super().__init__(message, retryable=True)


@contextmanager
def acquire_slot(db: Session):
    """选择一个账号并占用全局+账号并发槽位,退出时释放。

    yields (FlowCredential, FlowAccount)
    """
    r = get_sync_redis()
    now = datetime.now(timezone.utc)

    # 全局闸门
    global_count = r.incr(GLOBAL_KEY)
    if global_count == 1:
        r.expire(GLOBAL_KEY, 3600)
    if global_count > settings.FLOW_GLOBAL_CONCURRENCY:
        r.decr(GLOBAL_KEY)
        raise NoAccountAvailable("全局并发已满,请稍后重试")

    account: FlowAccount | None = None
    try:
        accounts = db.execute(
            select(FlowAccount).where(FlowAccount.status == AccountStatus.active)
        ).scalars().all()
        # 过滤冷却中的账号
        candidates = [
            a for a in accounts
            if not (a.cooldown_until and a.cooldown_until > now)
        ]
        if not candidates:
            raise NoAccountAvailable("没有可用账号")

        # 选当前占用率最低的(in_use / max_concurrency),加权打散
        def score(a: FlowAccount) -> float:
            in_use = int(r.get(ACCOUNT_KEY.format(account_id=a.id)) or 0)
            cap = max(1, a.max_concurrency)
            load = in_use / cap
            return load - (a.weight * 0.01)

        candidates.sort(key=score)

        for a in candidates:
            akey = ACCOUNT_KEY.format(account_id=a.id)
            cnt = r.incr(akey)
            if cnt == 1:
                r.expire(akey, 3600)
            if cnt <= a.max_concurrency:
                account = a
                break
            r.decr(akey)

        if account is None:
            raise NoAccountAvailable("所有账号并发已满")

        account.last_used_at = now
        db.commit()

        extra_headers = {}
        if account.extra_headers:
            try:
                extra_headers = json.loads(account.extra_headers)
            except (json.JSONDecodeError, TypeError):
                extra_headers = {}

        cred = FlowCredential(
            account_id=account.id,
            label=account.label,
            auth_token=account.auth_token,
            cookie=account.cookie,
            extra_headers=extra_headers,
        )
        yield cred, account
    finally:
        r.decr(GLOBAL_KEY)
        if account is not None:
            r.decr(ACCOUNT_KEY.format(account_id=account.id))


def mark_success(db: Session, account: FlowAccount) -> None:
    account.success_count += 1
    account.last_error = None
    db.commit()


def mark_failure(db: Session, account: FlowAccount, error: str, cooldown_seconds: int = 0) -> None:
    account.fail_count += 1
    account.last_error = error[:1000]
    if cooldown_seconds > 0:
        from datetime import timedelta

        account.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
        account.status = AccountStatus.cooldown
    db.commit()
