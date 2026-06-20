from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.enums import TaskType
from app.models.user import User
from app.schemas.user import QuotaUsage, UserOut
from app.services import quota

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/quota", response_model=QuotaUsage)
async def get_quota(user: User = Depends(get_current_user)):
    image_used = await quota.get_usage(user.id, TaskType.image)
    video_used = await quota.get_usage(user.id, TaskType.video)
    return QuotaUsage(
        daily_image_quota=user.daily_image_quota,
        daily_image_used=image_used,
        daily_video_quota=user.daily_video_quota,
        daily_video_used=video_used,
    )
