import enum


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class TaskType(str, enum.Enum):
    image = "image"
    video = "video"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AccountStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    cooldown = "cooldown"
    invalid = "invalid"
