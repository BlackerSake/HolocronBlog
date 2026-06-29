from pydantic_settings import BaseSettings

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
    
    # Railway 注入 postgresql:// → 自动转异步驱动
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

    # JWT 鉴权信息
    SECRET_KEY: str = "holocron_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 实例化配置对象
settings = Settings()


