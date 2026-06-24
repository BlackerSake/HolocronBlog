
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

import logging

logger = logging.getLogger(__name__)

router = APIRouter() # 路由,用来创建API
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    """密码加密,哈希值"""
    # 防御性截断到 72 字节（UTF-8)
    password_bytes = password.encode("utf-8")[:72]

    return pwd_context.hash(password)

@router.post("/register",
             response_model=UserOut, # 响应模型
             status_code=status.HTTP_201_CREATED) # 状态码
async def register(user_data: UserCreate,
                   db: AsyncSession = Depends(get_db),
                   ):
    # 检查用户名是否已存在
    existing_user = await db.execute(
        # 查询有没有用户名相同的用户
        select(User).where(User.username == user_data.username)
    )

    if existing_user.scalar_one_or_none(): # 如果已经存在
        logger.error(f"用户名'{user_data.username}'已存在")
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户实例(以 ORM 对象)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password=hash_password(user_data.password),
    )

    # ORM 添加并提交 (⚠️注意: 这里只是内存对象,提交之后才会写入数据库)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user) # 刷新对象, 获取自增id 和 时间
    return new_user
    