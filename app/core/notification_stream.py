
import asyncio
import logging
import socket
from contextlib import suppress
from typing import Any, cast
from redis.typing import StreamIdT
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.redis import redis_client
from app.services.notification_service import create_notification


NOTIFICATION_STREAM = "like:notification:events"
NOTIFICATION_GROUP = "notification-db-writers"
NOTIFICATION_GROUP_START_ID = "0"

NOTIFICATION_BATCH_SIZE = 100
NOTIFICATION_BLOCK_MS = 5000
NOTIFICATION_PENDING_IDLE_MS = 60_000
NOTIFICATION_STREAM_MAXLEN = 100_000

logger = logging.getLogger(__name__)

_notification_stream_task: asyncio.Task | None = None


def _decode(value: Any) -> str:
    """将 Redis 返回值统一转换为 str。"""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _decode_fields(fields: dict[Any, Any]) -> dict[str, str]:
    """将 Redis Stream fields 统一转换成 dict[str, str]。"""
    return {
        _decode(key): _decode(value)
        for key, value in fields.items()
    }


def _normalize_messages(
    messages: Any,
) -> list[tuple[str, dict[str, str]]]:
    """
    将 redis-py 返回的 Stream 消息统一转换成业务层使用的类型。

    Redis 实际格式：
        [(message_id, {field: value, ...}), ...]

    由于 redis-py 的类型定义比较宽泛，这里在 Redis 边界进行一次归一化。
    """
    result: list[tuple[str, dict[str, str]]] = []

    for message_id, fields in messages:
        result.append(
            (
                _decode(message_id),
                _decode_fields(fields),
            )
        )
    return result

async def append_notification_event(
    *,
    initiator_id: int,
    recipient_id: int,
    type: str,
    content: str,
    article_id: int | None = None,
    comment_id: int | None = None,
) -> str:
    """把点赞通知追加到 Stream，由后台消费者异步落库。

    接口侧只做这一件事：XADD。
    真正写 notifications 表 + 推送接收者
    WebSocket 都在消费者里完成。
    """
    message_id = await redis_client.xadd(
        NOTIFICATION_STREAM,
        {
            "initiator_id": str(initiator_id),
            "recipient_id": str(recipient_id),
            "type": type,
            "content": content,
            "article_id": str(article_id) if article_id is not None else "",
            "comment_id": str(comment_id) if comment_id is not None else "",
        },
        maxlen=NOTIFICATION_STREAM_MAXLEN,
        approximate=True,
    )
    return _decode(message_id)

async def _ensure_notification_group() -> None:
    """创建通知 Stream Group，已存在则忽略 BUSYGROUP。"""
    try:
        await redis_client.xgroup_create(
            NOTIFICATION_STREAM,
            NOTIFICATION_GROUP,
            id=NOTIFICATION_GROUP_START_ID,
            mkstream=True,
        )
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

def _opt_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None
async def _claim_stale_pending(
    consumer_name: str,
) -> list[tuple[str, dict[str, str]]]:
    """认领空闲超时的 pending 消息，用于失败重试。"""
    pending = await redis_client.xpending_range(
        NOTIFICATION_STREAM,
        NOTIFICATION_GROUP,
        min="-",
        max="+",
        count=NOTIFICATION_BATCH_SIZE,
    )

    ids: list[StreamIdT] = [
        cast(StreamIdT, item["message_id"])
        for item in pending
        if int(item.get("time_since_delivered", 0))
        >= NOTIFICATION_PENDING_IDLE_MS
    ]
    if not ids:
        return []

    claimed = await redis_client.xclaim(
        NOTIFICATION_STREAM,
        NOTIFICATION_GROUP,
        consumer_name,
        NOTIFICATION_PENDING_IDLE_MS,
        ids,
    )
    return _normalize_messages(claimed)


async def _read_messages(
    consumer_name: str,
) -> list[tuple[str, dict[str, str]]]:
    """先认领过期 pending，再读取新消息。"""

    stale = await _claim_stale_pending(consumer_name)
    if stale:
        return stale
    try:
        streams = await redis_client.xreadgroup(
            NOTIFICATION_GROUP,
            consumer_name,
            {NOTIFICATION_STREAM: ">"},
            count=NOTIFICATION_BATCH_SIZE,
            block=NOTIFICATION_BLOCK_MS,
        )
    except RedisTimeoutError:
        return []
    except ResponseError as e:
        if "NOGROUP" in str(e):
            await _ensure_notification_group()
            return []
        raise

    if not streams:
        return []

    messages: list[tuple[str, dict[str, str]]] = []

    for _, stream_messages in streams:
        messages.extend(_normalize_messages(stream_messages))

    return messages


async def _persist_notifications(
    db: AsyncSession,
    messages: list[tuple[str, dict[str, str]]],
) -> None:
    """逐条落库 + XACK；失败回滚并留 pending 等待重试。"""
    for message_id, fields in messages:
        try:
            await create_notification(
                db,
                initiator_id=int(fields["initiator_id"]),
                recipient_id=int(fields["recipient_id"]),
                type=fields["type"],
                content=fields["content"],
                article_id=_opt_int(fields.get("article_id")),
                comment_id=_opt_int(fields.get("comment_id")),
            )
        except Exception:
            logger.exception(
                "通知落库失败，留 pending 重试: %s",
                message_id,
            )

            await db.rollback()
            continue

        await redis_client.xack(
            NOTIFICATION_STREAM,
            NOTIFICATION_GROUP,
            message_id,
        )


async def _notification_stream_loop() -> None:
    await _ensure_notification_group()
    from app.core.database import create_engine
    engine = create_engine()

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    consumer_name = (
        f"{socket.gethostname()}:notif:{id(asyncio.current_task())}"
    )

    try:
        while True:
            messages = await _read_messages(consumer_name)
            if not messages:
                continue
            async with session_factory() as db:
                await _persist_notifications(db, messages)
    except asyncio.CancelledError:
        logger.info("通知 Stream consumer 已取消")
    finally:
        await engine.dispose()


async def run_notification_stream_worker() -> None:
    """独立 consumer 进程入口，用于和 API worker 做 workload isolation。"""
    await _notification_stream_loop()


async def start_notification_stream_task() -> None:
    global _notification_stream_task

    if (
        _notification_stream_task
        and not _notification_stream_task.done()
    ):
        return

    _notification_stream_task = asyncio.create_task(
        _notification_stream_loop()
    )


async def stop_notification_stream_task() -> None:
    global _notification_stream_task
    if not _notification_stream_task:
        return
    _notification_stream_task.cancel()
    with suppress(asyncio.CancelledError):
        await _notification_stream_task
    _notification_stream_task = None


if __name__ == "__main__":
    asyncio.run(run_notification_stream_worker())
