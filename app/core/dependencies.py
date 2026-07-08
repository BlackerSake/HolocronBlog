from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.services.permission_service import get_current_user_permissions

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 JWT 令牌中解析并获取当前认证用户。

    解码令牌获取用户名，从数据库加载用户记录，并检查用户是否被禁用。

    Args:
        token: OAuth2 Bearer 令牌，由 FastAPI 自动从请求头提取。
        db: 异步数据库会话，由 FastAPI 依赖注入提供。

    Returns:
        User: 当前认证用户对象。

    Raises:
        HTTPException 401: 令牌无效、过期或用户不存在。
        HTTPException 403: 用户已被禁用。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="验证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户被禁用")
    return user


def require_permission(permission: str) -> Callable:
    """
    权限检查依赖工厂。

    返回一个 FastAPI 依赖项，用于校验当前用户是否拥有指定权限字符串。
    若权限不足则返回 403。

    Args:
        permission: 所需权限字符串，如 "article:create"。

    Returns:
        Callable: 可注入的 FastAPI 依赖函数，返回 User 对象或抛出 403。
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        permissions = await get_current_user_permissions(current_user)
        if permission not in permissions:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return _check
