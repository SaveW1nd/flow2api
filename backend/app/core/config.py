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
    MEDIA_DIR: str = "media"
    MEDIA_PUBLIC_ENDPOINT: str = "http://localhost:18000/media"

    # First admin
    FIRST_ADMIN_EMAIL: str = "admin@flow2api.local"
    FIRST_ADMIN_PASSWORD: str = "admin12345"

    # FLOW adapter
    FLOW_GLOBAL_CONCURRENCY: int = 8
    FLOW_PER_ACCOUNT_CONCURRENCY: int = 2
    FLOW_REQUEST_TIMEOUT: int = 120
    FLOW_VIDEO_MAX_WAIT: int = 600
    FLOW_VIDEO_POLL_INTERVAL: int = 3
    # 用 curl_cffi 模拟 Chrome TLS 指纹(需安装 curl_cffi);impersonate 取本机 curl_cffi 支持的版本
    FLOW_USE_CURL: bool = True
    FLOW_IMPERSONATE: str = "chrome124"
    # reCAPTCHA 引擎:优先使用无头 Chrome broker 执行官方 Enterprise JS,纯 HTTP anchor/reload 作为兜底。
    FLOW_HEADLESS: bool = False
    FLOW_CHROME_PATH: str = ""
    FLOW_PROFILES_DIR: str = "/data/flow_profiles"
    FLOW_TOKEN_TIMEOUT: int = 90
    # 全局默认代理(账号可单独覆盖)。格式:http://user:pass@host:port 或 socks5://user:pass@host:port
    # 关键:reCAPTCHA broker/协议请求与 Flow HTTP 提交会走同一代理 -> 同一出口 IP,避免 token/请求 IP 不一致被判异常。
    FLOW_PROXY: str = ""
    # reCAPTCHA 分数有波动:每次失败重新取新 token 重试,重试期间不冷却账号。
    FLOW_RECAPTCHA_RETRIES: int = 5
    FLOW_RECAPTCHA_RETRY_DELAY: int = 4
    # 鉴权失败/限流账号的冷却秒数
    FLOW_AUTH_COOLDOWN: int = 120
    FLOW_QUOTA_COOLDOWN: int = 3600

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
