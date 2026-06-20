from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    daily_image_quota: int
    daily_video_quota: int
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None
    daily_image_quota: int | None = None
    daily_video_quota: int | None = None


class QuotaUsage(BaseModel):
    daily_image_quota: int
    daily_image_used: int
    daily_video_quota: int
    daily_video_used: int
