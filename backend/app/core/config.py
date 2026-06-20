from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    # General
    PROJECT_NAME: str = "Flow2API"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    # Security
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # Database
    POSTGRES_USER: str = "flow"
    POSTGRES_PASSWORD: str = "flow_pass"
    POSTGRES_DB: str = "flow2api"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # S3 / MinIO
    S3_ENDPOINT: str = "http://minio:9000"
    S3_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "flow2api"
    S3_REGION: str = "us-east-1"

    # First admin
    FIRST_ADMIN_EMAIL: str = "admin@flow2api.local"
    FIRST_ADMIN_PASSWORD: str = "admin12345"

    # FLOW adapter
    FLOW_GLOBAL_CONCURRENCY: int = 8
    FLOW_PER_ACCOUNT_CONCURRENCY: int = 2
    FLOW_REQUEST_TIMEOUT: int = 120
    FLOW_VIDEO_MAX_WAIT: int = 600

    # Quota / rate limit
    DEFAULT_DAILY_IMAGE_QUOTA: int = 200
    DEFAULT_DAILY_VIDEO_QUOTA: int = 20
    USER_RATE_LIMIT_PER_MIN: int = 30

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sqlalchemy_sync_uri(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS", mode="before")
    @classmethod
    def _to_int(cls, v):
        return int(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
