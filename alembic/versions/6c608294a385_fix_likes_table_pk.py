"""fix likes table pk — remove target_type from composite primary key

SQLite 不支持 ALTER TABLE 修改主键，需要 recreate 表。

Revision ID: 6c608294a385
Revises: 16ce6cfa73c9
Create Date: 2026-07-07 14:35:19.248703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6c608294a385'
down_revision: Union[str, Sequence[str], None] = '16ce6cfa73c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # recreate likes table — drop composite pk, keep id as single pk
    op.create_table(
        "likes_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("create_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="unique_like_per_user_per_target"),
    )
    op.create_index(op.f("ix_likes_new_target_id"), "likes_new", ["target_id"])

    # copy data
    op.execute("INSERT INTO likes_new (id, user_id, target_type, target_id, create_at) SELECT id, user_id, target_type, target_id, create_at FROM likes")

    # swap
    op.drop_table("likes")
    op.rename_table("likes_new", "likes")


def downgrade() -> None:
    # restore composite pk
    op.create_table(
        "likes_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("create_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", "target_type"),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="unique_like_per_user_per_target"),
    )
    op.create_index(op.f("ix_likes_old_target_id"), "likes_old", ["target_id"])

    op.execute("INSERT INTO likes_old (id, user_id, target_type, target_id, create_at) SELECT id, user_id, target_type, target_id, create_at FROM likes")

    op.drop_table("likes")
    op.rename_table("likes_old", "likes")
