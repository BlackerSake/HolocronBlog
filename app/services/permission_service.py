




import json

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
    permissions = {p.name for p in user.role_obj.permissions}

    # 3. 写入 redis
    await cache_user_permissions(user.id, permissions)

    return permissions

async def get_cached_permissions(user_id: int) -> set[str] | None:
    """缓存读取: 从 redis 缓存中获取权限字符串合集"""
    key = f"{PERMISSION_CACHE_PREFIX}{user_id}"
    data = await redis_client.get(key)
    if data is None:
        return None
    return set(json.loads(data))

async def cache_user_permissions(user_id: int, permissions: set[str]) -> None:
    """缓存写入: 将权限字符串合集写入 redis"""
    key = f"{PERMISSION_CACHE_PREFIX}{user_id}"
    await redis_client.set(key, json.dumps(list(permissions)), ex=CACHE_TTL)

async def delete_user_permissions(user_id: int) -> None:
    """缓存删除: 删除用户权限缓存"""
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
    return user.id == owner_id or permission in await get_current_user_permissions(user)
    
    
