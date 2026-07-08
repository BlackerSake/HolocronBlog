
import logging
import asyncio
import socket
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from redis import ResponseError
from typing import cast
from app.core.config import settings
from app.core.redis import redis_client
from app.services.like_service import _set_like_status_in_db

LIKE_STREAM = "like:events"
LIKE_GROUP = "like-db-writers"
LIKE_BATCH_SIZE = 100
LIKE_BLOCK_MS = 5000
LIKE_PENDING_IDLE_MS = 60_000

logger = logging.getLogger(__name__)

_like_stream_task: asyncio.Task | None = None # 后台任务句柄, 用于在应用关闭时取消任务

async def append_like_event(user_id: int, target_id: int, 
                            target_type: str, is_liked: bool) -> str:
    """将点赞事件追加到 Redis Stream 中"""
    result = await redis_client.xadd(LIKE_STREAM,{
        "user_id": user_id,
        "target_id": target_id,
        "target_type": target_type,
        "is_liked": int(is_liked), # 将布尔值转化为0/1
    })
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
        await redis_client.xgroup_create(LIKE_STREAM, LIKE_GROUP, id="0", mkstream=True) 
    except ResponseError as e:
        # 如果 Group 已经存在, 则忽略错误
        if "BUSYGROUP" not in str(e):
            raise # 此时group创建失败,且不存在, 抛出异常

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
async def _claim_stale_pending(consumer_name: str) -> list[tuple[str, dict]]:
    """
    ## 认领过期的 Pending 消息
    - consumer_name: 当前消费者的名字
    - 返回: [(message_id, fields), ...]
    """
    # 1. 获取 Pending 消息列表
    pending = await redis_client.xpending_range(
        LIKE_STREAM, LIKE_GROUP, min="-", max="+", count=LIKE_BATCH_SIZE
    )
    # 2. 筛选出过期的 Pending 消息
    
    ids = [
        item["message_id"]
        for item in pending
        # cast: 将 item["time_since_delivered"] 转换为 int,*确保是int之间比较*
        if cast(int, item["time_since_delivered"]) >= LIKE_PENDING_IDLE_MS
    ]

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
    streams = await redis_client.xreadgroup(
        LIKE_GROUP,
        consumer_name,
        {LIKE_STREAM: ">"},
        count=LIKE_BATCH_SIZE,
        block=LIKE_BLOCK_MS,
    )
    return _flatten(streams)

async def _flush_to_db(messages: list[tuple[str, dict]],db: AsyncSession) -> None:
    """
    ## 将消息写入数据库
    - 批量写入数据库
    - 批量更新 Redis Stream 的 Pending 状态
    """
    ids, latest = _dedupe(messages) # 去重

    for (user_id, target_type, target_id), is_liked in latest.items():
        await _set_like_status_in_db(
            db, user_id, target_id, target_type, is_liked
        )
    await db.commit()
    await redis_client.xack(LIKE_STREAM, LIKE_GROUP, *ids)

async def _like_stream_task_loop() -> None:
    """
    ## Like Stream 任务循环
    - 确保 Like Stream Group 存在
    - 循环读取消息, 并批量写入数据库
    - 若读取消息失败, 则回滚等待 pending 重试
    """
    await _ensure_like_group()

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession) # 关闭自动提交
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
                    # 如果发生异常, 则回滚
                    await db.rollback()
                    logger.exception("点赞事件批量写入数据库失败, 等待pending重试...")
                    await asyncio.sleep(1) 
    except asyncio.CancelledError: # 如果任务被取消, 则忽略错误
        logger.info("点赞 Stream consumer 任务已取消")
    finally:
        await engine.dispose() # 释放引擎
    
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