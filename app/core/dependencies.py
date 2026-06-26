from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.token import TokenData

"""依赖注入

"""
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """依赖: 从token中获取用户信息"""

    # 1. 验证token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="验证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # 2. 获取用户信息
    try: 
        payload = jwt.decode(
            token, # 要解码的token
            settings.SECRET_KEY, # 密钥
            algorithms=[settings.ALGORITHM], # 加密算法
        )
        username: str = payload.get("sub") 
        # 获取用户名,sub 是jwt中定义的用户名字段

        if username is None:
            raise credentials_exception
        
        token_data = TokenData(username=username) 
        # 创建TokenData对象
    except JWTError:
        raise credentials_exception
    

    # 从数据库查询角色
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户被禁用")
    return user


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    ## 获取当前用户role
    确保当前用户为管理员
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="权限不足"
        )
    return current_user

