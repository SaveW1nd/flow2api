"""Prompt 去重缓存：复用过去相同 prompt + 相同 params 的 succeeded 任务输出，
避免重复消耗 Google credits 与等待时间。

策略：
- 缓存按 (type, prompt, params) 精确匹配（PG JSONB 等值）。
- 命中时复制旧 task 的 outputs（URL 列表，由 storage 层托管，长期有效），
  在新 task 上直接标记 succeeded，跳过 Celery。
- 跨用户共享：A 用户生成过，B 用户同 prompt 命中。新 task 的 user_id 仍是请求者。
- num_outputs / seed / extra 都计入 params 一并匹配；想让缓存失效在 extra 加个唯一字段即可。
- 设 PROMPT_CACHE_ENABLED=0 关闭。
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus, TaskType
from app.models.generation import GenerationTask


def cache_enabled() -> bool:
    return os.getenv("PROMPT_CACHE_ENABLED", "1") not in ("0", "false", "False", "no")


async def find_cached_outputs(
    db: AsyncSession,
    *,
    task_type: TaskType,
    prompt: str,
    params: dict[str, Any],
) -> tuple[int, list[dict[str, Any]]] | None:
    """查最近一条同 prompt + 同 params 的 succeeded 任务。
    返回 (source_task_id, outputs) 或 None。
    """
    if not cache_enabled():
        return None
    # 命中条件：完全相同的 prompt、params（JSONB 等值）、状态 succeeded、有输出。
    stmt = (
        select(GenerationTask.id, GenerationTask.outputs)
        .where(
            GenerationTask.type == task_type,
            GenerationTask.prompt == prompt,
            GenerationTask.params == params,
            GenerationTask.status == TaskStatus.succeeded,
            func.jsonb_array_length(GenerationTask.outputs) > 0,
        )
        .order_by(desc(GenerationTask.created_at))
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return row[0], list(row[1] or [])
