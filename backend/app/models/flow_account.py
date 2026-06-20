from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import AccountStatus


class FlowAccount(Base):
    """A pool of FLOW upstream accounts/tokens used by the adapter layer."""

    __tablename__ = "flow_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)

    # Reverse-engineered auth material (token / cookie / refresh). Stored as text.
    auth_token: Mapped[str] = mapped_column(Text, nullable=False)
    cookie: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_headers: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, length=20),
        default=AccountStatus.active,
        nullable=False,
    )
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
