from logging.config import fileConfig
import asyncio
from sqlalchemy import pool

from alembic import context
from alembic.operations import ops
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.core.config import settings
from app.core.database import Base as ModelsBase
import app.models  # noqa: F401 — registers all tables on Base.metadata



# 将异步驱动 URL 转为 Alembic 可用的同步 URL
sync_db_url = (
    settings.DATABASE_URL
    .replace("postgresql+asyncpg://", "postgresql://")
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = ModelsBase.metadata



def _iter_ops(container):
    for operation in getattr(container, "ops", []):
        yield operation
        yield from _iter_ops(operation)


def _describe_destructive_op(operation) -> str:
    if isinstance(operation, ops.DropTableOp):
        return f"drop table {operation.table_name}"
    if isinstance(operation, ops.DropColumnOp):
        return f"drop column {operation.table_name}.{operation.column_name}"
    return operation.__class__.__name__


def reject_destructive_autogenerate(context, revision, directives) -> None:
    """阻止 autogenerate 误生成会丢数据的删表/删列迁移。"""
    if not getattr(getattr(config, "cmd_opts", None), "autogenerate", False):
        return

    destructive = [
        _describe_destructive_op(operation)
        for directive in directives
        for operation in _iter_ops(directive.upgrade_ops)
        if isinstance(operation, (ops.DropTableOp, ops.DropColumnOp))
    ]
    if destructive:
        raise RuntimeError(
            "Alembic autogenerate produced destructive operations: "
            + ", ".join(destructive)
            + ". Write this migration by hand after backing up the database."
        )

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,          # 直接用 asyncpg URL
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        process_revision_directives=reject_destructive_autogenerate,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        process_revision_directives=reject_destructive_autogenerate,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
