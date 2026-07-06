"""add_user_profile_fields

Revision ID: 8f4c2b6d9a10
Revises: 2102487aff82
Create Date: 2026-07-06 12:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f4c2b6d9a10"
down_revision: Union[str, Sequence[str], None] = "2102487aff82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ROLES = {
    "admin": {
        "description": "管理员角色",
        "is_system": True,
        "permissions": {
            "article:create",
            "article:update",
            "article:delete",
            "article:publish",
            "article:unpublish",
            "comment:create",
            "comment:delete",
            "category:manage",
            "tag:manage",
            "user:manage",
            "role:manage",
            "upload:create",
            "broadcast:create",
        },
    },
    "author": {
        "description": "作者角色",
        "is_system": True,
        "permissions": {
            "article:create",
            "article:update",
            "article:delete",
            "article:publish",
            "article:unpublish",
            "comment:create",
            "comment:delete",
            "tag:manage",
            "upload:create",
        },
    },
    "user": {
        "description": "用户角色",
        "is_system": True,
        "permissions": {"comment:create", "upload:create"},
    },
}


def _seed_default_roles() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("create_at", sa.DateTime),
    )
    role_permission = sa.table(
        "role_permission",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    permission_ids = {}
    all_permissions = sorted(
        {perm for cfg in DEFAULT_ROLES.values() for perm in cfg["permissions"]}
    )
    for name in all_permissions:
        permission_id = bind.execute(
            sa.select(permissions.c.id).where(permissions.c.name == name)
        ).scalar()
        if permission_id is None:
            bind.execute(
                permissions.insert().values(
                    name=name,
                    description=name,
                    created_at=now,
                )
            )
            permission_id = bind.execute(
                sa.select(permissions.c.id).where(permissions.c.name == name)
            ).scalar_one()
        permission_ids[name] = permission_id

    for name, cfg in DEFAULT_ROLES.items():
        role_id = bind.execute(
            sa.select(roles.c.id).where(roles.c.name == name)
        ).scalar()
        if role_id is None:
            bind.execute(
                roles.insert().values(
                    name=name,
                    description=cfg["description"],
                    is_system=cfg["is_system"],
                    create_at=now,
                )
            )
            role_id = bind.execute(
                sa.select(roles.c.id).where(roles.c.name == name)
            ).scalar_one()

        for perm_name in cfg["permissions"]:
            permission_id = permission_ids[perm_name]
            exists = bind.execute(
                sa.select(role_permission.c.role_id).where(
                    role_permission.c.role_id == role_id,
                    role_permission.c.permission_id == permission_id,
                )
            ).first()
            if not exists:
                bind.execute(
                    role_permission.insert().values(
                        role_id=role_id,
                        permission_id=permission_id,
                    )
                )


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("nick_name", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("avatar", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(length=255), nullable=True))
    _seed_default_roles()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "bio")
    op.drop_column("users", "avatar")
    op.drop_column("users", "nick_name")
