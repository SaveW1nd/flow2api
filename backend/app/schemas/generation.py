from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskStatus, TaskType


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str | None = None
    aspect_ratio: str = "1:1"
    num_outputs: int = Field(default=1, ge=1, le=4)
    seed: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    duration: int = Field(default=5, ge=2, le=20)
    aspect_ratio: str = "16:9"
    resolution: str = "VIDEO_RESOLUTION_1080P"
    image_url: str | None = None  # 图生视频可选首帧
    seed: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    type: TaskType
    status: TaskStatus
    progress: int
    prompt: str
    params: dict[str, Any]
    outputs: list[dict[str, Any]]
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class TaskCreatedOut(BaseModel):
    public_id: str
    status: TaskStatus
    type: TaskType


class TaskListOut(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int
