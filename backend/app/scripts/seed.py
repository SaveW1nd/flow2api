"""初始化:建表 + 创建初始管理员。

用法: python -m app.scripts.seed
"""

from sqlalchemy import select

from app.core.config import settings
from app.core.db import Base
from app.core.db_sync import SyncSessionLocal, sync_engine
from app.core.security import hash_password
from app.models import *  # noqa: F401,F403
from app.models.enums import UserRole
from app.models.user import User


def main() -> None:
    Base.metadata.create_all(bind=sync_engine)
    with SyncSessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == settings.FIRST_ADMIN_EMAIL))
        if existing:
            print(f"管理员已存在: {existing.email}")
            return
        admin = User(
            email=settings.FIRST_ADMIN_EMAIL,
            full_name="Administrator",
            hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
            role=UserRole.admin,
            daily_image_quota=100000,
            daily_video_quota=100000,
        )
        db.add(admin)
        db.commit()
        print(f"已创建管理员: {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")


if __name__ == "__main__":
    main()
