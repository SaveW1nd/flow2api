"""Celery 任务:出图 / 出视频。

执行流程:
1. 取任务记录,标记 running,推进度。
2. 通过账号池占用并发槽位,选号。
3. 调用 FLOW 适配层(异步内部用 asyncio.run 跑),失败时换账号重试。
4. 把结果资源转存对象存储,落库,推完成进度。
5. 失败则记录错误、退还额度、推失败进度。
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from celery import shared_task

from app.core.db_sync import SyncSessionLocal
from app.models.enums import TaskStatus, TaskType
from app.models.generation import GenerationTask
from app.services.flow.client import FlowClient, FlowError
from app.services.flow.pool import (
    NoAccountAvailable,
    acquire_slot,
    mark_failure,
    mark_success,
)
from app.services.progress import publish_progress
from app.services.storage import store_remote_asset

MAX_ACCOUNT_RETRIES = 3


def _push(task: GenerationTask, status: TaskStatus, progress: int, error: str | None = None):
    publish_progress(
        task.public_id,
        {
            "public_id": task.public_id,
            "status": status.value,
            "progress": progress,
            "outputs": task.outputs,
            "error": error,
        },
    )


def _attempt_once(db, task: GenerationTask, task_type: TaskType) -> bool:
    """占用一个账号槽位执行一次生成。成功返回 True;失败抛出 FlowError 由上层换号。"""
    with acquire_slot(db) as (cred, account):
        task.account_id = account.id
        db.commit()
        client = FlowClient(cred)

        def progress_cb(p: int):
            task.progress = p
            db.commit()
            _push(task, TaskStatus.running, p)

        try:
            if task_type == TaskType.image:
                _push(task, TaskStatus.running, 30)
                result = asyncio.run(client.submit_image(task.prompt, task.params))
            else:
                result = asyncio.run(client.submit_video(task.prompt, task.params, progress_cb))
        except FlowError as exc:
            # 鉴权失效 / 限流时让该账号冷却,避免反复命中坏号
            cooldown = 120 if exc.status_code in (401, 403, 429) else 0
            mark_failure(db, account, str(exc), cooldown_seconds=cooldown)
            raise

        # 转存到对象存储
        task.progress = 96
        db.commit()
        _push(task, TaskStatus.running, 96)
        stored = []
        for out in result.outputs:
            url = store_remote_asset(out["url"], out["type"], task.user_id)
            stored.append({"url": url, "type": out["type"]})

        task.outputs = stored
        task.status = TaskStatus.succeeded
        task.progress = 100
        task.finished_at = datetime.now(timezone.utc)
        db.commit()
        mark_success(db, account)
        _push(task, TaskStatus.succeeded, 100)
        return True


def _run_generation(task_id: int, task_type: TaskType) -> None:
    db = SyncSessionLocal()
    try:
        task = db.get(GenerationTask, task_id)
        if task is None or task.status in (TaskStatus.cancelled,):
            return

        task.status = TaskStatus.running
        task.started_at = datetime.now(timezone.utc)
        task.progress = 5
        db.commit()
        _push(task, TaskStatus.running, 5)

        last_error: str | None = None
        for _attempt in range(MAX_ACCOUNT_RETRIES):
            try:
                ok = _attempt_once(db, task, task_type)
                if ok:
                    return
            except NoAccountAvailable as exc:
                last_error = str(exc)
                time.sleep(2)  # 等待其他任务释放槽位后重试
                continue
            except FlowError as exc:
                last_error = str(exc)
                if not exc.retryable:
                    break
                continue

        # 全部重试失败
        task.status = TaskStatus.failed
        task.error = last_error or "生成失败"
        task.finished_at = datetime.now(timezone.utc)
        db.commit()
        _push(task, TaskStatus.failed, task.progress, error=task.error)

        # 退还额度
        _refund(task)
    finally:
        db.close()


def _refund(task: GenerationTask) -> None:
    """同步上下文里退还额度(直接操作 Redis)。"""
    from datetime import datetime as _dt

    from app.services.flow.pool import get_sync_redis

    r = get_sync_redis()
    date = _dt.now(timezone.utc).strftime("%Y%m%d")
    key = f"quota:daily:{task.user_id}:{task.type.value}:{date}"
    r.decr(key)


@shared_task(name="tasks.generate_image", bind=True, max_retries=0)
def generate_image(self, task_id: int) -> None:
    _run_generation(task_id, TaskType.image)


@shared_task(name="tasks.generate_video", bind=True, max_retries=0)
def generate_video(self, task_id: int) -> None:
    _run_generation(task_id, TaskType.video)
