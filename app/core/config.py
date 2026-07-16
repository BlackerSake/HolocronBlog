from pydantic_settings import BaseSettings
from zoneinfo import ZoneInfo


_DEFAULT_SECRET_KEY = "holocron_secret_key"


class Settings(BaseSettings):
    # 应用的基本信息
    APP_NAME: str = "Holocron Blog"
    APP_DESCRIPTION: str = "This is my blog (config)"
    APP_VERSION: str = "0.5.0"

    # 数据库信息，本地默认 SQLite
    DATABASE_URL: str = "sqlite+aiosqlite:///./holocron.db"

    # Redis 信息
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_SYNC_INTERVAL: int = 60 * 5
    LIKE_STREAM_IN_PROCESS: bool = True

    # Railway 注入 postgresql:// → 自动转异步驱动
    def __init__(self, **kwargs):
        """
        初始化配置，自动转换数据库 URL 并验证生产环境密钥。

        若 DATABASE_URL 以 postgresql:// 开头，自动替换为 postgresql+asyncpg://
        以启用异步驱动。生产环境（PostgreSQL）下强制要求通过环境变量设置 SECRET_KEY。

        Args:
            **kwargs: 传递给 BaseSettings 的父类参数。

        Raises:
            ValueError: 生产环境使用默认 SECRET_KEY 时抛出。
        """
        super().__init__(**kwargs)
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        # 生产环境必须通过环境变量设置 SECRET_KEY
        if self.DATABASE_URL.startswith("postgresql") and self.SECRET_KEY == _DEFAULT_SECRET_KEY:
            raise ValueError(
                "生产环境必须通过环境变量 SECRET_KEY 设置 JWT 密钥，不能使用默认值"
            )

    # JWT 鉴权信息
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS 允许的来源，逗号分隔；默认本地开发地址
    CORS_ORIGINS: str = "http://localhost:8848,https://localhost:8848,http://127.0.0.1:8848,https://127.0.0.1:8848,http://localhost:5173,http://127.0.0.1:5173"

    # 时区
    TIMEZONE: str = "Asia/Shanghai"

    @property
    def tz(self) -> ZoneInfo:
        """获取配置时区对应的 ZoneInfo 对象。"""
        return ZoneInfo(self.TIMEZONE)

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS_ORIGINS 字符串拆分为列表，并去除空白。"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 实例化配置对象
settings = Settings()
