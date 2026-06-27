"""add article views column

Revision ID: 9c8e2b1f4a5d
Revises: 06d06d07edf7
Create Date: 2026-06-27 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c8e2b1f4a5d"
down_revision: Union[str, None] = "06d06d07edf7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("views", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("articles", "views")
