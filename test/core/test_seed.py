from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import seed as seed_mod
from app.core.permissions import DEFAULT_ROLES
from app.models.role import Role, role_permission


async def test_seed_default_roles_restores_missing_role(monkeypatch, db_session):
    factory = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(seed_mod, "AsyncSessionLocal", factory)

    author = (
        await db_session.execute(select(Role).where(Role.name == "author"))
    ).scalar_one()
    await db_session.execute(
        role_permission.delete().where(role_permission.c.role_id == author.id)
    )
    await db_session.execute(Role.__table__.delete().where(Role.id == author.id))
    await db_session.commit()

    await seed_mod.seed_default_roles()

    roles = (await db_session.execute(select(Role.name))).scalars().all()
    assert set(DEFAULT_ROLES) <= set(roles)
