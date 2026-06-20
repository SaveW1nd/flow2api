from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccountStatus


class FlowAccountCreate(BaseModel):
    label: str
    auth_token: str
    cookie: str | None = None
    refresh_token: str | None = None
    extra_headers: str | None = None
    weight: int = 1
    max_concurrency: int = 2


class FlowAccountUpdate(BaseModel):
    label: str | None = None
    auth_token: str | None = None
    cookie: str | None = None
    refresh_token: str | None = None
    extra_headers: str | None = None
    status: AccountStatus | None = None
    weight: int | None = None
    max_concurrency: int | None = None


class FlowAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    status: AccountStatus
    weight: int
    max_concurrency: int
    success_count: int
    fail_count: int
    last_error: str | None
    last_used_at: datetime | None
    created_at: datetime
