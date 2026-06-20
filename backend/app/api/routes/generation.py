import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.enums import TaskStatus, TaskType
from app.models.generation import GenerationTask
from app.models.user import User
from app.schemas.generation import (
    ImageGenerateRequest,
    TaskCreatedOut,
    TaskListOut,
    TaskOut,
    VideoGenerateRequest,
)
from app.services import quota
from app.workers.tasks import generate_image, generate_video

router = APIRouter(prefix="/generate", tags=["generation"])


async def _create_task(
    db: AsyncSession,
    user: User,
    task_type: TaskType,
    prompt: str,
    params: dict,
    num: int,
) -> GenerationTask:
    await quota.check_rate_limit(user.id)
    limit = user.daily_image_quota if task_type == TaskType.image else user.daily_video_quota
    await quota.consume_quota(user.id, task_type, limit, amount=num)

    task = GenerationTask(
        public_id=str(uuid.uuid4()),
        user_id=user.id,
        type=task_type,
        status=TaskStatus.queued,
        prompt=prompt,
        params=params,
        outputs=[],
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.post("/image", response_model=TaskCreatedOut)
async def create_image(
    payload: ImageGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    params = payload.model_dump(exclude={"prompt"})
    task = await _create_task(
        db, user, TaskType.image, payload.prompt, params, payload.num_outputs
    )
    await db.commit()
    async_result = generate_image.delay(task.id)
    task.celery_task_id = async_result.id
    await db.commit()
    return TaskCreatedOut(public_id=task.public_id, status=task.status, type=task.type)


@router.post("/video", response_model=TaskCreatedOut)
async def create_video(
    payload: VideoGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    params = payload.model_dump(exclude={"prompt"})
    task = await _create_task(db, user, TaskType.video, payload.prompt, params, 1)
    await db.commit()
    async_result = generate_video.delay(task.id)
    task.celery_task_id = async_result.id
    await db.commit()
    return TaskCreatedOut(public_id=task.public_id, status=task.status, type=task.type)


@router.get("/tasks", response_model=TaskListOut)
async def list_tasks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: TaskType | None = None,
):
    stmt = select(GenerationTask).where(GenerationTask.user_id == user.id)
    count_stmt = select(func.count()).select_from(GenerationTask).where(
        GenerationTask.user_id == user.id
    )
    if type:
        stmt = stmt.where(GenerationTask.type == type)
        count_stmt = count_stmt.where(GenerationTask.type == type)

    total = await db.scalar(count_stmt) or 0
    stmt = stmt.order_by(GenerationTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.scalars(stmt)).all()
    return TaskListOut(
        items=[TaskOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tasks/{public_id}", response_model=TaskOut)
async def get_task(
    public_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await db.scalar(
        select(GenerationTask).where(
            GenerationTask.public_id == public_id, GenerationTask.user_id == user.id
        )
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task
