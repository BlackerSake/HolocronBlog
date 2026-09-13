#!/usr/bin/env python3
"""一次性 SQLite → PostgreSQL 数据迁移(保留原始 id)。

从根目录 holocron.db 读取业务数据,写入 benchmark PostgreSQL。按外键依赖
顺序拷贝,显式写入原始 id,最后按 max(id) 重置自增 sequence。

前提:目标 PG 已由 `alembic upgrade head` 建好空表。

用法:
  set -a; source .env.bench; set +a
  python scripts/migrate_sqlite_to_pg.py

可安全重复执行:开头 TRUNCATE 所有目标表并重启 identity。
"""
import asyncio
import os
from datetime import datetime, timezone

import asyncpg
import sqlite3

SQLITE_PATH = os.getenv("SQLITE_PATH", "holocron.db")
# 优先取 DATABASE_URL(经 .env.bench source 后),剥掉 +asyncpg 供 asyncpg 直连
PG_DSN = os.getenv("PG_DSN") or os.getenv(
    "DATABASE_URL",
    "postgresql://skywalker:bench@localhost:15432/holocron",
).replace("postgresql+asyncpg://", "postgresql://")

# 表 → (列名, 布尔列, 无时区时间列, 带时区时间列);顺序即外键依赖顺序
TABLES: dict[str, tuple[list[str], set[str], set[str], set[str]]] = {
    "roles":          (["id", "name", "description", "is_system", "create_at"],
                       {"is_system"}, {"create_at"}, set()),
    "permissions":    (["id", "name", "description", "created_at"],
                       set(), {"created_at"}, set()),
    "role_permission": (["role_id", "permission_id"], set(), set(), set()),
    "users":          (["id", "username", "role_id", "email", "password",
                        "is_active", "nickname", "avatar", "bio", "created_at"],
                       {"is_active"}, {"created_at"}, set()),
    "categories":     (["id", "name", "description", "created_at"],
                       set(), {"created_at"}, set()),
    "tags":           (["id", "name", "created_at"], set(), {"created_at"}, set()),
    "articles":       (["id", "title", "slug", "content", "content_html",
                        "summary", "cover_image", "is_published", "is_deleted",
                        "created_at", "updated_at", "views", "like_count",
                        "author_id", "category_id"],
                       {"is_published", "is_deleted"}, set(),
                       {"created_at", "updated_at"}),
    "article_tags":   (["article_id", "tag_id"], set(), set(), set()),
    "comments":       (["id", "content", "article_id", "author_id", "parent_id",
                        "is_published", "is_deleted", "created_at", "like_count"],
                       {"is_published", "is_deleted"}, set(), {"created_at"}),
    "likes":          (["id", "user_id", "target_type", "target_id", "create_at"],
                       set(), {"create_at"}, set()),
    "notifications":  (["id", "type", "initiator_id", "recipient_id", "article_id",
                        "comment_id", "content", "preview", "is_read", "created_at"],
                       {"is_read"}, set(), {"created_at"}),
}

# 有自增 id sequence 的表(role_permission / article_tags 是复合主键,无 sequence)
SERIAL_TABLES = [t for t in TABLES if t not in ("role_permission", "article_tags")]


def _convert(table: str, col: str, value):
    """把 SQLite 的值转成 asyncpg 能编码的 Python 类型。"""
    if value is None:
        return None
    _, bools, naivedt, tzdt = TABLES[table]
    if col in bools:
        return bool(int(value))  # SQLite 布尔以 0/1 存储
    if col in naivedt or col in tzdt:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"无法解析时间 {table}.{col}={value!r}") from exc
        if col in tzdt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)  # 带时区列补 UTC
        if col in naivedt and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)  # 无时区列剥掉偏移
        return dt
    return value


def _read_table(con: sqlite3.Connection, table: str):
    cols, bools, naivedt, tzdt = TABLES[table]
    # 评论有自引用 parent_id,按 id 升序保证父评论先插入
    order = " ORDER BY id" if table == "comments" else ""
    rows = con.execute(
        f'SELECT {", ".join(cols)} FROM "{table}"{order}'
    ).fetchall()
    records = [
        tuple(_convert(table, c, v) for c, v in zip(cols, row)) for row in rows
    ]
    return cols, records


async def main() -> None:
    con = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)
    conn = await asyncpg.connect(PG_DSN)

    try:
        # 可重跑:清空所有目标表,restart identity 复位 sequence
        await conn.execute(
            f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"
        )
        print(f"已清空目标表: {', '.join(TABLES)}\n")

        for table in TABLES:
            cols, records = _read_table(con, table)
            if not records:
                print(f"{table:18s} 0 行 (跳过)")
                continue
            await conn.copy_records_to_table(
                table, records=records, columns=cols
            )
            print(f"{table:18s} {len(records)} 行")

        # 显式写入 id 不会推进 sequence,按 max(id) 重置
        print("\n重置自增 sequence:")
        for table in SERIAL_TABLES:
            await conn.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    (SELECT COALESCE(MAX(id), 1) FROM {table}),
                    (SELECT COUNT(*) > 0 FROM {table})
                )
                """
            )
            max_id = await conn.fetchval(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
            print(f"  {table:18s} → {max_id}")
    finally:
        await conn.close()
        con.close()


if __name__ == "__main__":
    asyncio.run(main())
