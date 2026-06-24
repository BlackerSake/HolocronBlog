from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用的基本信息
    APP_NAME: str = "Holocron Blog"
    APP_DESCRIPTION: str = "This is my blog (config)"
    APP_VERSION: str = "0.0.1"

    # 数据库信息 先硬编码 SQLlite, 方便直接跑  后期再换PostgreSQL
    DATABASE_URL: str = "sqlit+aiosqlite:///./holocorn.db"
    
    # JWT 鉴权信息
    SECRET_KEY: str = "holocron_secret_key" # 密钥, 以后换到.env
    ALGORITHM: str = "HS256" # JWT 使用的加密算法
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # JWT 访问令牌过期时间

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 实例化配置对象,即创建一个全局的设置对象
settings = Settings()


