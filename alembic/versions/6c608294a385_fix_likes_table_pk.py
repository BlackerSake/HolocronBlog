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
    #
    # 注意: 唯一约束先不在建表时创建。PostgreSQL 中命名约束是 schema 级对象,
    # 旧 likes 仍持有 unique_like_per_user_per_target 时,likes_new 再建同名会报
    # DuplicateTable; 因此先建裸表、拷贝、换名,最后再补约束(此时旧表已 drop)。
    op.create_table(
        "likes_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("create_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_likes_new_target_id"), "likes_new", ["target_id"])

    # copy data
    op.execute("INSERT INTO likes_new (id, user_id, target_type, target_id, create_at) SELECT id, user_id, target_type, target_id, create_at FROM likes")

    # swap
    op.drop_table("likes")
    op.rename_table("likes_new", "likes")

    op.create_unique_constraint(
        "unique_like_per_user_per_target",
        "likes",
        ["user_id", "target_type", "target_id"],
    )


def downgrade() -> None:
    # restore composite pk (同样的命名约束时序问题,约束放到换名之后补)
    op.create_table(
        "likes_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("create_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", "target_type"),
    )
    op.create_index(op.f("ix_likes_old_target_id"), "likes_old", ["target_id"])

    op.execute("INSERT INTO likes_old (id, user_id, target_type, target_id, create_at) SELECT id, user_id, target_type, target_id, create_at FROM likes")

    op.drop_table("likes")
    op.rename_table("likes_old", "likes")

    op.create_unique_constraint(
        "unique_like_per_user_per_target",
        "likes",
        ["user_id", "target_type", "target_id"],
    )
