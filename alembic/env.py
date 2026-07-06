from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.operations import ops
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import Base as ModelsBase
import app.models  # noqa: F401 — registers all tables on Base.metadata



# 将异步驱动 URL 转为 Alembic 可用的同步 URL
sync_db_url = (
    settings.DATABASE_URL
    .replace("sqlite+aiosqlite://", "sqlite://")
    .replace("postgresql+asyncpg://", "postgresql://")
)


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# 设置 target_metadata
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
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=sync_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        process_revision_directives=reject_destructive_autogenerate,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        {"sqlalchemy.url": sync_db_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            process_revision_directives=reject_destructive_autogenerate,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
