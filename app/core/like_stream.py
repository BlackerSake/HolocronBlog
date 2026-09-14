
import logging
import asyncio
import socket
from sqlalchemy import delete, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError
from typing import cast
from app.core.config import settings
from app.core.redis import redis_client
from app.models.article import Article
from app.models.comment import Comment
from app.models.like import Likes

LIKE_STREAM = "like:events"
LIKE_DEADLETTER_STREAM = "like:events:deadletter"
LIKE_GROUP = "like-db-writers"
LIKE_GROUP_START_ID = "0"
LIKE_BATCH_SIZE = 100
LIKE_BLOCK_MS = 5000
LIKE_PENDING_IDLE_MS = 60_000
LIKE_MAX_RETRIES = 3
LIKE_STREAM_MAXLEN = 200_000

logger = logging.getLogger(__name__)

_like_stream_task: asyncio.Task | None = None # 后台任务句柄, 用于在应用关闭时取消任务

async def append_like_event(user_id: int, target_id: int, 
                            target_type: str, is_liked: bool) -> str:
    """将点赞事件追加到 Redis Stream 中

    该函数保留给手动补偿和测试场景；正常点赞链路由 Lua 脚本在同一次
    EVAL 内完成状态变更和 XADD，避免 旧数据被覆盖
    """
    result = await redis_client.xadd(LIKE_STREAM,{
        "user_id": user_id,
        "target_id": target_id,
        "target_type": target_type,
        "is_liked": int(is_liked), # 将布尔值转化为0/1
    }, maxlen=LIKE_STREAM_MAXLEN, approximate=True)
    assert isinstance(result, str) # 确保返回的是str
    return result

async def _ensure_like_group() -> None:
    """
    ## 确保 Like Stream Group 存在  
    try 创建 Redis Stream Group  -> 创建成功/失败  
    创建失败:   
     -> 如果**已经存在** 则忽略错误
     -> 如果**不存在** 则抛出异常
    """
    try: 
        # 创建 Like Stream Group, 
        await redis_client.xgroup_create(LIKE_STREAM, LIKE_GROUP, id=LIKE_GROUP_START_ID, mkstream=True) 
    except ResponseError as e:
        # 如果 Group 已经存在, 则忽略错误
        if "BUSYGROUP" not in str(e):
            raise  # 非 BUSYGROUP 异常透传抛出

def _flatten(streams) -> list[tuple[str, dict]]:
    """将 Redis Stream 返回的嵌套列表展平为 [(id, dict), ...]"""
    messages = []
    for _, stream_messages in streams:
        messages.extend(stream_messages)
    return messages

def _dedupe(messages: list[tuple[str, dict]]) -> tuple[list[str], dict[tuple[int, str, int], bool]]:
    """
    ## 对 Redis Stream 消息去重
    - messages: [(message_id, fields), ...]
    - fields: {"user_id": str, "target_type": str, "target_id": str, "is_liked": str}
    - 返回: (message_ids, latest_dict)
    - latest_dict: {(user_id, target_type, target_id): is_liked, ...}
    如果同一个用户对同一个目标有多条消息, 只保留最新的一条, 其他的丢弃
    """
    ids = []
    latest = {}
    for message_id, fields in messages:
        ids.append(message_id)
        key = (int(fields["user_id"]), fields["target_type"], int(fields["target_id"]))
        latest[key] = bool(int(fields["is_liked"]))
    return ids, latest

async def _move_pending_to_deadletter(message_id: str, reason: str) -> None:
    """
    ## 死信队列
    将 poison message 转移到 DLQ，并 ACK 原始 pending message
    """
    rows = await redis_client.xrange(LIKE_STREAM,
                                     min=message_id,
                                     max=message_id,
                                     count=1)
    fields = {}
    if rows:
        fields = rows[0][1]
    payload = {
        **fields,
        "source_id": message_id,
        "reason": reason,
    }
    await redis_client.xadd(
        LIKE_DEADLETTER_STREAM,
        payload,
        maxlen=LIKE_STREAM_MAXLEN,
        approximate=True,
    )
    await redis_client.xack(LIKE_STREAM, LIKE_GROUP, message_id)

async def _claim_stale_pending(consumer_name: str) -> list[tuple[str, dict]]:
    """
    ## 认领过期的 Pending 消息
    - consumer_name: 当前消费者的名字
    - 返回: [(message_id, fields), ...]
    - 副作用: 超过 LIKE_MAX_RETRIES 的 poison message 自动转入 DLQ
    """
    # 1. 获取 Pending 消息列表
    pending = await redis_client.xpending_range(
        LIKE_STREAM, LIKE_GROUP, min="-", max="+", count=LIKE_BATCH_SIZE
    )
    # 2. 筛选：超限消息进 DLQ，超时消息 claim
    
    ids = []
    for item in pending:
        message_id = cast(str, item["message_id"])
        # cast: 将 item["time_since_delivered"] 转换为 int,*确保是int之间比较*
        idle_ms = cast(int, item["time_since_delivered"])
        deliveries = int(item.get("times_delivered", 0))
        if deliveries >= LIKE_MAX_RETRIES:
            await _move_pending_to_deadletter(message_id, "max_retries_exceeded")
            continue
        if idle_ms >= LIKE_PENDING_IDLE_MS:
            ids.append(message_id)

    if not ids:
        return []
    result =  await redis_client.xclaim(
        LIKE_STREAM, LIKE_GROUP, consumer_name, LIKE_PENDING_IDLE_MS, ids
    )
    return cast(list[tuple[str, dict]], result) # 类型转换

async def _read_messages(consumer_name: str) -> list[tuple[str, dict]]:
    """
    ## 从 Redis Stream 中读取消息
    - consumer_name: 当前消费者的名字
    - 返回: [(message_id, fields), ...]
    """
    # 1. 先认领过期的 Pending 消息
    pending = await _claim_stale_pending(consumer_name)
    if pending:
        return pending
    # 2. 如果没有过期的 Pending 消息, 则读取新的消息
    # 阻塞读可能撞上客户端 socket 超时: 视为空轮询,下轮重试
    try:
        streams = await redis_client.xreadgroup(
            LIKE_GROUP,
            consumer_name,
            {LIKE_STREAM: ">"},
            count=LIKE_BATCH_SIZE,
            block=LIKE_BLOCK_MS,
        )
    except RedisTimeoutError:
        return []
    except ResponseError as e:
        if "NOGROUP" in str(e):
            await _ensure_like_group()
            return []
        raise
    return _flatten(streams)

async def _persist_latest_states(db: AsyncSession,
                                 latest: dict[tuple[int, str, int], bool]) -> None:
    """批量持久化最新点赞状态，并按实际变更聚合更新 like_count"""
    if not latest:
        return

    keys = list(latest)
    # 一次查询：获取已存在的所有点赞记录
    rows = await db.execute(
        select(Likes.user_id, Likes.target_type, Likes.target_id).where(
            tuple_(Likes.user_id, Likes.target_type, Likes.target_id).in_(keys)
        )
    )
    existing = {tuple(row) for row in rows.all()}
    to_insert = []
    to_delete = []
    deltas: dict[tuple[str, int], int] = {}

    for key, is_liked in latest.items():
        user_id, target_type, target_id = key
        if is_liked and key not in existing:
            to_insert.append(
                Likes(user_id=user_id, target_id=target_id, target_type=target_type)
            )
            deltas[(target_type, target_id)] = deltas.get((target_type, target_id), 0) + 1
        elif not is_liked and key in existing:
            to_delete.append(key)
            deltas[(target_type, target_id)] = deltas.get((target_type, target_id), 0) - 1

    if to_insert:
        db.add_all(to_insert)
    if to_delete:
        await db.execute(
            delete(Likes).where(
                tuple_(Likes.user_id, Likes.target_type, Likes.target_id).in_(to_delete)
            )
        )

    for (target_type, target_id), delta in deltas.items():
        model = Article if target_type == "article" else Comment
        await db.execute(
            update(model)
            .where(model.id == target_id)
            .values(like_count=model.like_count + delta)
        )

async def _flush_to_db(messages: list[tuple[str, dict]],db: AsyncSession) -> None:
    """
    ## 将去重后的消息批量写入数据库，并确认已消费

    使用乐观批处理：一次查询已有记录 → 内存比对 → 批量 INSERT/DELETE → 单次 commit。
    避免逐条 SELECT + 逐条 commit 的 N 倍 DB 开销。
    """
    ids, latest = _dedupe(messages) # 去重

    await _persist_latest_states(db, latest)
    await db.commit()
    await redis_client.xack(LIKE_STREAM, LIKE_GROUP, *ids)

async def _like_stream_task_loop() -> None:
    """
    ## Like Stream 任务循环
    - 确保 Like Stream Group 存在
    - 循环读取消息, 并批量写入数据库
    - 若批量写入失败, 则回滚会话,消息留在 pending 列表等待下次重试
    """
    await _ensure_like_group()

    #engine = create_async_engine(settings.DATABASE_URL)
    from app.core.database import create_engine
    engine = create_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession) # 允许 commit 后继续使用 session 中的对象
    consumer_name = f"{socket.gethostname()}:{id(asyncio.current_task())}"

    try: 
        while True:
            messages = await _read_messages(consumer_name)
            if not messages:
                continue

            async with session_factory() as db: # 创建会话
                try:
                    await _flush_to_db(messages, db) # 批量写入数据库
                except Exception:
                    # flush 失败时回滚,消息留在 pending 列表中,下次循环重试
                    await db.rollback()
                    logger.exception("点赞事件批量写入数据库失败, 等待pending重试...")
                    await asyncio.sleep(1) 
    except asyncio.CancelledError: # 如果任务被取消, 则忽略错误
        logger.info("点赞 Stream consumer 任务已取消")
    finally:
        await engine.dispose() # 释放引擎

async def run_like_stream_worker() -> None:
    """独立 consumer 进程入口，用于和 API worker 做 workload isolation"""
    await _like_stream_task_loop()
    
async def start_like_stream_task() -> None:
    """
    ## 启动 Like Stream 任务
    - 创建并启动 Like Stream 批量写入数据库的任务
    """
    global _like_stream_task
    _like_stream_task = asyncio.create_task(_like_stream_task_loop())

async def stop_like_stream_task() -> None:
    """
    ## 停止 Like Stream 批量写入数据库的任务
    """
    if not _like_stream_task:
        return
    _like_stream_task.cancel()
    try:
        await _like_stream_task # 等待任务取消
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(run_like_stream_worker())
