

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
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
    """用户列表查询+分页，附带角色信息，返回 (items, total)"""
    query = select(User)

    if role_name:
        query = query.join(Role).where(Role.name == role_name)
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
            role=RoleOut.model_validate(u.role_obj),
        ))
    return items, total