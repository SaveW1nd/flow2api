"""开发环境快速建表(生产请使用 alembic 迁移)。

用法: python -m app.scripts.init_db
"""

from app.core.db import Base
from app.core.db_sync import sync_engine
from app.models import *  # noqa: F401,F403


def main() -> None:
    Base.metadata.create_all(bind=sync_engine)
    print("数据库表已创建/校验完成。")


if __name__ == "__main__":
    main()
