from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "flow2api",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    task_default_queue="image",
    task_routes={
        "tasks.generate_image": {"queue": "image"},
        "tasks.generate_video": {"queue": "video"},
    },
    task_time_limit=settings.FLOW_VIDEO_MAX_WAIT + 120,
    task_soft_time_limit=settings.FLOW_VIDEO_MAX_WAIT + 60,
)

# 确保任务被注册
from app.workers import tasks  # noqa: E402,F401
