import json
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.models.role import Role
from app.models.user import User
from app.services.permission_service import get_current_user_permissions

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

USER_AUTH_CACHE_PREFIX = "cache:user:auth:"
USER_AUTH_CACHE_TTL = 60  # 短 TTL:禁用/改角色靠主动失效兜底,TTL 只兜遗漏


def _user_cache_key(username: str) -> str:
    return f"{USER_AUTH_CACHE_PREFIX}{username}"


async def invalidate_user_cache(username: str) -> None:
    """用户资料/角色/禁用状态变更后调用,Redis 故障时 fail-open 等 TTL 过期"""
    try:
        await redis_client.delete(_user_cache_key(username))
    except Exception:
        pass


def _user_from_cache(data: dict) -> User:
    """从缓存字段重建脱离 session 的 User,并挂上只含名称的 Role 桩对象

    访问桩对象上未缓存的字段(如 role_obj.permissions)会抛
    DetachedInstanceError,由调用方(permission_service)回源 db。
    """
    user = User(
        id=data["id"],
        username=data["username"],
        email=data["email"],
        role_id=data["role_id"],
        is_active=data["is_active"],
        nickname=data["nickname"],
        avatar=data["avatar"],
        bio=data["bio"],
    )
    user.role_obj = Role(id=data["role_id"], name=data["role_name"])
    return user


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

    # 优先读 Redis 用户缓存,命中则免去每请求的 users 表查询
    cache_key = _user_cache_key(username)
    user: User | None = None
    try:
        cached = await redis_client.get(cache_key)
    except Exception:
        cached = None  # Redis 故障 fail-open 走 db
    if cached is not None:
        user = _user_from_cache(json.loads(cached))
    else:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        try:
            await redis_client.set(cache_key, json.dumps({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role_id": user.role_id,
                "role_name": user.role_obj.name,
                "is_active": user.is_active,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "bio": user.bio,
            }), ex=USER_AUTH_CACHE_TTL)
        except Exception:
            pass
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
