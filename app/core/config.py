from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "holocron_secret_key"

# 用绝对路径定位 .env，避免 CWD 不同导致读不到
_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "Holocron Blog"
    APP_DESCRIPTION: str = "This is my blog (config)"
    APP_VERSION: str = "0.5.0"

    DATABASE_URL: str = "postgresql+asyncpg:///./holocron.db"
    REDIS_URL: str = ""
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_SYNC_INTERVAL: int = 60 * 5
    LIKE_STREAM_IN_PROCESS: bool = True
    RATE_LIMIT_ENABLED: bool = True
    BACKGROUND_TASKS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: str = (
        "http://localhost:8848,https://localhost:8848,"
        "http://127.0.0.1:8848,https://127.0.0.1:8848,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    TIMEZONE: str = "Asia/Shanghai"

    model_config = SettingsConfigDict(
        env_file=str(_BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _normalize_and_check(self):
        # 统一到异步驱动
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"本项目已全面使用 PostgreSQL，但 DATABASE_URL={self.DATABASE_URL!r} 不是 postgresql+asyncpg://"
            )
        # 生产密钥校验
        if self.SECRET_KEY == _DEFAULT_SECRET_KEY:
            raise ValueError(
                "必须通过环境变量 SECRET_KEY 设置 JWT 密钥，不能使用默认值"
            )
        return self


settings = Settings()
