

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    async_sessionmaker, 
    AsyncSession)
from sqlalchemy.orm import declarative_base
from app.core.config import settings

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


# 创建异步引擎 : 构建一个 engine 对象，让所有代码连接到同一个数据库
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # 切关闭, 由log控制
)

# 创建异步会话工厂: 一个可调用对象
# 每次调用会从engine里提取一个空闲的连接, 并包装成一个异步会话对象
AsyncSessionLocal = async_sessionmaker(
    bind=engine, # 绑定引擎
    class_=AsyncSession, # 使用异步会话
    expire_on_commit=False # 不自动提交
)

# 创建基类,供所有模型继承
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话，用于 FastAPI 依赖注入。

    Yields:
        AsyncSession: 自动管理生命周期数据库会话对象。
    """
    async with AsyncSessionLocal() as session:
        yield session
