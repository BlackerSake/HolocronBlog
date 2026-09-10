




import json

from sqlalchemy import select
from sqlalchemy.orm.exc import DetachedInstanceError

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.redis import redis_client

PERMISSION_CACHE_PREFIX = "user:permissions:"
CACHE_TTL = 60 * 30


async def get_current_user_permissions(user: User) -> set[str]:
    """
    ### 获取当前登录用户 的所有权限字符串合集
    优先从 redis 缓存读取, 若未命中 -> 通过 ORM懒加载查询数据库 
    """
    # 1. 获取 redis 缓存
    cached = await get_cached_permissions(user.id)

    if cached:
        return cached
    # 2. redis 缓存未命中 -> 查询数据库
    # user 可能来自 auth 缓存(脱离 session),此时懒加载抛 DetachedInstanceError,回源 db
    try:
        permissions = {p.name for p in user.role_obj.permissions}
    except DetachedInstanceError:
        async with AsyncSessionLocal() as db:
            db_user = await db.get(User, user.id)
            if db_user is None:
                return set()
            permissions = {p.name for p in db_user.role_obj.permissions}

    # 3. 写入 redis
    await cache_user_permissions(user.id, permissions)

    return permissions

async def get_cached_permissions(user_id: int) -> set[str] | None:
    """从 Redis 缓存中读取用户权限字符串集合

    Args:
        user_id: 用户 ID

    Returns:
        权限集合，若缓存未命中则返回 None
    """
    key = f"{PERMISSION_CACHE_PREFIX}{user_id}"
    data = await redis_client.get(key)
    if data is None:
        return None
    return set(json.loads(data))

async def cache_user_permissions(user_id: int, permissions: set[str]) -> None:
    """将用户权限集合写入 Redis 缓存，有效期 30 分钟

    Args:
        user_id: 用户 ID
        permissions: 权限字符串集合
    """
    key = f"{PERMISSION_CACHE_PREFIX}{user_id}"
    await redis_client.set(key, json.dumps(list(permissions)), ex=CACHE_TTL)

async def delete_user_permissions(user_id: int) -> None:
    """删除指定用户的权限 Redis 缓存

    通常用于权限变更后强制下次请求重新加载。

    Args:
        user_id: 用户 ID
    """
    key = f"{PERMISSION_CACHE_PREFIX}{user_id}"
    await redis_client.delete(key)

async def change_user_permissions(user_id: int, permissions: set[str]) -> None:
    """
    ## 缓存更新: 用户权限变更, 批量删除缓存
    1. 查询该users 表, 拿到所有该user的角色
    2. 批量删除用户权限缓存
    """
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            select(User.id).where(User.id == user_id)
        )
        user_ids = result.scalars().all()

    for uid in user_ids:
        await delete_user_permissions(uid)


async def if_owner_or_permission(user: User, owner_id: int, permission: str) -> bool:
    """判断当前用户是否为资源所有者或拥有指定权限

    用于访问控制：若用户是资源所有者则直接放行，
    否则检查是否具备所需权限字符串。

    Args:
        user: 当前登录用户
        owner_id: 资源所有者的用户 ID
        permission: 所需的权限字符串（如 "article:create"）

    Returns:
        布尔值，True 表示有权限访问
    """
    return user.id == owner_id or permission in await get_current_user_permissions(user)
    
    
