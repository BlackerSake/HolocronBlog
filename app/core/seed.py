"""初始化种子数据：默认角色和权限"""
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.permission import Permission
from app.models.role import Role, role_permission
from app.core.permissions import ALL_PERMISSIONS, DEFAULT_ROLES

logger = logging.getLogger(__name__)


async def seed_default_roles() -> None:
    """补齐默认角色、权限和关联关系。"""
    async with AsyncSessionLocal() as db:
        changed = False
        perm_map = {}
        for perm_name in ALL_PERMISSIONS:
            existing = await db.execute(
                select(Permission).where(Permission.name == perm_name)
            )
            perm = existing.scalar_one_or_none()
            if not perm:
                perm = Permission(name=perm_name, description=perm_name)
                db.add(perm)
                await db.flush()
                changed = True
            perm_map[perm_name] = perm

        for name, cfg in DEFAULT_ROLES.items():
            existing = await db.execute(
                select(Role).where(Role.name == name)
            )
            role = existing.scalar_one_or_none()
            if not role:
                role = Role(
                    name=name,
                    description=cfg["description"],
                    is_system=cfg["is_system"],
                )
                db.add(role)
                await db.flush()
                changed = True

            for perm_name in cfg["permissions"]:
                perm = perm_map.get(perm_name)
                if perm:
                    existing_link = await db.execute(
                        select(role_permission.c.role_id).where(
                            role_permission.c.role_id == role.id,
                            role_permission.c.permission_id == perm.id,
                        )
                    )
                    if existing_link.first():
                        continue
                    await db.execute(
                        role_permission.insert().values(
                            role_id=role.id,
                            permission_id=perm.id,
                        )
                    )
                    changed = True

        await db.commit()
        if changed:
            logger.info("默认角色和权限已补齐")
