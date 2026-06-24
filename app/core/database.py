

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
    # Bug-1 FastAPI 的依赖注入可以接受异步生成器，但返回类型需要标注为 AsyncGenerator 
    # 因为函数里有 yield，它是一个异步生成器，返回类型应该是 AsyncGenerator[AsyncSession, None]，而不是直接返回 AsyncSession。
    """在路由中 获取数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session
