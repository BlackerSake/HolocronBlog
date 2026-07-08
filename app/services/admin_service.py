

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import RoleOut, UserWithRoleList


async def query_all_user_role(
    db: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 20,
    role_name: str | None = None,
    search: str | None = None,
) -> tuple[list[UserWithRoleList], int]:
    """查询所有用户及其角色信息，支持分页、按角色和关键词搜索

    用于后台管理：以列表形式展示用户信息，可按角色名筛选
    或按用户名/邮箱模糊搜索。

    Args:
        db: 数据库会话
        page: 页码，从 1 开始
        per_page: 每页条数
        role_name: 按角色名称筛选
        search: 按用户名或邮箱模糊搜索

    Returns:
        (用户列表（含角色信息）, 总条数) 的元组
    """
    query = select(User)

    if role_name:
        query = query.join(User.role_obj).where(Role.name == role_name)
    if search:
        query = query.where(or_(
            User.username.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
        ))

    total = (await db.execute(
        select(func.count()).select_from(query.subquery())
    )).scalar()

    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    items = []
    for u in result.scalars().all():
        items.append(UserWithRoleList(
            id=u.id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            created_at=u.created_at,
            role=RoleOut.model_validate(u.role_obj),
        ))
    return items, total