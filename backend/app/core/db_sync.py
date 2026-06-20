"""同步数据库会话,供 Celery worker 使用(worker 内不跑 asyncio 事件循环)。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

sync_engine = create_engine(
    settings.sqlalchemy_sync_uri,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, expire_on_commit=False)
