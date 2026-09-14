"""store timestamps as UTC-aware values

Revision ID: 3d1e7f9a2b4c
Revises: 6c608294a385
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d1e7f9a2b4c"
down_revision: Union[str, Sequence[str], None] = "6c608294a385"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TIMESTAMP_COLUMNS = {
    "users": ("created_at",),
    "categories": ("created_at",),
    "tags": ("created_at",),
    "roles": ("create_at",),
    "permissions": ("created_at",),
    "articles": ("created_at", "updated_at"),
    "comments": ("created_at",),
    "notifications": ("created_at",),
    "likes": ("create_at",),
}
_LEGACY_TIMEZONES = {"roles": "UTC", "permissions": "UTC"}


def _alter_timestamps(to_timestamptz: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("The UTC timestamp migration requires PostgreSQL")

    for table, columns in _TIMESTAMP_COLUMNS.items():
        for column in columns:
            data_type = bind.execute(
                sa.text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            ).scalar_one()
            if to_timestamptz:
                legacy_timezone = _LEGACY_TIMEZONES.get(table, "Asia/Shanghai")
                using = (
                    f'"{column}" AT TIME ZONE \'{legacy_timezone}\''
                    if data_type == "timestamp without time zone"
                    else f'"{column}"'
                )
                target_type = "TIMESTAMPTZ"
            else:
                using = f'"{column}" AT TIME ZONE \'Asia/Shanghai\''
                target_type = "TIMESTAMP WITHOUT TIME ZONE"
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                    f"TYPE {target_type} USING {using}"
                )
            )


def upgrade() -> None:
    _alter_timestamps(True)


def downgrade() -> None:
    _alter_timestamps(False)
