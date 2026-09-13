import asyncio
from contextlib import suppress
import json
import logging
import time
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.like_stream import LIKE_STREAM, LIKE_STREAM_MAXLEN
from app.core.redis import redis_client
from app.models.article import Article
from app.models.comment import Comment
from app.models.like import Likes
from app.models.user import User
from app.services.ranking_service import bump_article_hot_score
logger = logging.getLogger(__name__)

# Lua 原子设置目标状态，并在状态实际变化时写入 Stream。
_SET_LIKE_STATE_LUA = """
local desired = tonumber(ARGV[5])
local changed

if desired == 1 then
    changed = redis.call("SADD", KEYS[1], ARGV[1])
else
    changed = redis.call("SREM", KEYS[1], ARGV[1])
end

local count = redis.call("SCARD", KEYS[1])
if changed == 1 then
    redis.call(
        "XADD", KEYS[2], "MAXLEN", "~", ARGV[4], "*",
        "user_id", ARGV[1],
        "target_id", ARGV[2],
        "target_type", ARGV[3],
        "is_liked", desired
    )
end

return {desired, count, changed}
"""

LIKE_TARGET_CACHE_PREFIX = "cache:like_target:article:"
LIKE_TARGET_CACHE_TTL = 60           # slug→(id, author_id, like_count) 映射 TTL,变更由 invalidate_article_cache 主动失效
LIKE_CACHE_TTL = 60 * 30             # 缓存 TTL: 30 分钟，统一过期防止幽灵状态
LIKE_INIT_LOCK_TTL = 5               # 预热分布式锁超时: 5 秒，防止死锁
LIKE_REDIS_BREAKER_THRESHOLD = 5     # 连续 5 次 Redis 失败 → 熔断打开
LIKE_REDIS_BREAKER_RESET_SECONDS = 30  # 熔断后 30 秒进入半开状态,放行探测请求
LIKE_WARM_CHANNEL_PREFIX = "like:warmed"
LIKE_WARM_WAIT_SECONDS = 1.0

_redis_failure_count = 0
_redis_breaker_opened_at = 0.0
_warm_events: dict[str, asyncio.Event] = {}
_warm_listener_task: asyncio.Task | None = None

class LikeCacheWarmupError(RuntimeError):
    """点赞缓存预热未完成,调用方应 fail-fast 并降级到 DB 路径"""


def _redis_breaker_allows_request() -> bool:
    """
    ## 判断 Redis 点赞实时链路是否允许请求进入
    熔断器三态: CLOSED → OPEN → HALF_OPEN → CLOSED
    - CLOSED:  正常,所有请求走 Redis
    - OPEN:    连续 LIKE_REDIS_BREAKER_THRESHOLD 次失败 → 熔断打开,全部走 DB
    - HALF_OPEN: LIKE_REDIS_BREAKER_RESET_SECONDS 后放行一个探测请求,
                 成功则回到 CLOSED,失败则回到 OPEN
    当前阶段: 进程内计数器;多 worker 下每个进程独立计数,
    生产级应用应改用 Redis 存储熔断状态实现全局共享
    """
    if _redis_failure_count < LIKE_REDIS_BREAKER_THRESHOLD:
        return True
    return time.monotonic() - _redis_breaker_opened_at >= LIKE_REDIS_BREAKER_RESET_SECONDS


def _record_redis_success() -> None:
    """记录 Redis 点赞实时链路成功,关闭熔断"""
    global _redis_failure_count, _redis_breaker_opened_at
    _redis_failure_count = 0
    _redis_breaker_opened_at = 0.0


def _record_redis_failure() -> None:
    """记录 Redis 点赞实时链路失败,连续失败后进入 OPEN 状态"""
    global _redis_failure_count, _redis_breaker_opened_at
    _redis_failure_count += 1
    if _redis_failure_count >= LIKE_REDIS_BREAKER_THRESHOLD:
        _redis_breaker_opened_at = time.monotonic()


def _like_keys(target_id: int, target_type: str) -> tuple[str, str, str]:
    """生成点赞功能使用的 Redis 键名元组

    Args:
        target_id: 目标对象 ID（文章或评论）
        target_type: 目标类型（"article" 或 "comment"）

    Returns:
        (用户集合键, 已加载标记键, 初始化锁键) 三元组
    """
    base = f"like:{target_type}:{target_id}"
    return (
        f"{base}:users",
        f"{base}:loaded",
        f"{base}:init_lock",
    )
def _like_warm_channel(target_id: int, target_type: str) -> str:
    """生成点赞缓存预热完成事件的 Pub/Sub 频道"""
    return f"{LIKE_WARM_CHANNEL_PREFIX}:{target_id}:{target_type}"
def _get_warm_event(channel: str) -> asyncio.Event:
    """获取当前worker内某个预热频道对应的本地event"""
    event = _warm_events.get(channel)
    if event is None:
        event = asyncio.Event()
        _warm_events[channel] = event
    return event

async def _publish_like_warmed(target_id: int, target_type: str) -> None:
    """广播某个点赞缓存key已经完成预热,唤醒其他worker的等待协程"""
    channel = _like_warm_channel(target_id, target_type)
    _get_warm_event(channel).set()
    await redis_client.publish(channel, "1")

async def _like_warm_pubsub_loop() -> None:
    """
    ## 监听 Redis Pub/Sub 预热完成事件,并唤醒当前worker内的等待协程
    尝试监听所有频道,若当前worker内没有对应的预热事件则创建一个
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{LIKE_WARM_CHANNEL_PREFIX}:*")
    
    try:
        async for message in pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            channel = message["channel"]
            # 若当前worker内没有对应的预热事件则创建一个
            if isinstance(channel, bytes):
                channel = channel.decode()
            _get_warm_event(channel).set()
    except asyncio.CancelledError:
        raise
    finally: # 确保退出时取消订阅:finally块确保执行
        with suppress(Exception): # 抑制异常并执行接下来的语句
            await pubsub.punsubscribe(f"{LIKE_WARM_CHANNEL_PREFIX}:*") # 取消订阅
        with suppress(Exception):
            await pubsub.close()

async def start_like_warm_listener() -> None:
    """启动当前worker内的点赞预热 pub/sub 监听"""
    global _warm_listener_task
    # 如果监听任务已存在且未完成,则不重复启动
    if _warm_listener_task and not _warm_listener_task.done():
        return
    _warm_listener_task = asyncio.create_task(_like_warm_pubsub_loop())

async def stop_like_warm_listener() -> None:
    """停止当前worker内的点赞预热 pub/sub 监听"""
    global _warm_listener_task
    if not _warm_listener_task:
        return
    
    _warm_listener_task.cancel()
    with suppress(asyncio.CancelledError):
        await _warm_listener_task
    _warm_listener_task = None


async def _get_target_like_count(db: AsyncSession, target_id: int, target_type: str) -> int:
    """从数据库查询目标的点赞总数（兜底备用）

    Args:
        db: 数据库会话
        target_id: 目标对象 ID
        target_type: 目标类型（"article" 或 "comment"）

    Returns:
        点赞计数值,若目标不存在则返回 0
    """
    model = Article if target_type == "article" else Comment
    count = await db.scalar(select(model.like_count).where(model.id == target_id))
    return int(count or 0)


async def _warm_like_cache(db: AsyncSession, target_id: int, target_type: str) -> None:
    """
    ## 缓存预热(懒加载 + 分布式锁防止缓存击穿)
    ### 分布式锁 + Pub/Sub 广播
    - 第一个拿到锁的请求去 查db 并写入缓存
    - 其他请求等待redis Pub/Sub广播,等锁释放后直接读取缓存
    - 自旋超时未就绪则抛出 LikeCacheWarmupError,调用方降级到 DB 路径
    - 缓存 TTL: LIKE_CACHE_TTL（30 分钟），loaded / users 统一过期
    Args:
        db: 数据库会话
        target_id: 目标对象 ID
        target_type: 目标类型（"article" 或 "comment"）
    """
    users_key, loaded_key, lock_key = _like_keys(target_id, target_type)
    if await redis_client.exists(loaded_key):
        return

    locked = await redis_client.set(lock_key, "1", nx=True, ex=LIKE_INIT_LOCK_TTL)
    # 抢锁, 若失败则短暂自旋等待,避免缓存击穿
    # NX:只有键不存在时才设置成功. 用以保证互斥
    # EX: 锁过期时间 LIKE_INIT_LOCK_TTL 秒,防止死锁. 二者结合保证进程崩了,锁自动释放,
    if not locked:
        # 没抢到锁,即锁其他进程抢占. 等待redis Pub/Sub广播 避免自旋轮询
        channel = _like_warm_channel(target_id, target_type)
        event = _get_warm_event(channel)

        try:
            await asyncio.wait_for(event.wait(),timeout=LIKE_WARM_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        if await redis_client.exists(loaded_key):
            return
        # 还没预热完毕,抛出异常让上层降级到 DB 路径
        raise LikeCacheWarmupError(f"攒点缓存预热失败: {target_type}:{target_id}")
    """
    缓存预热
    故引入**Redis Pub/Sub缓存失效广播**:对于每个worker维护一个asyncio.Event
    预热完成之后publish 事件like:warmed:{target_id} 其他的worker通过Pub/Sub广播唤醒,无需自旋轮询
    """


    # 抢到锁 -> 查询db 并写入 redis 缓存
    try:
        if await redis_client.exists(loaded_key):
            return
        result = await db.execute(
            select(Likes.user_id).where(
                Likes.target_id == target_id,
                Likes.target_type == target_type,
            )
        )
        user_ids = [str(user_id) for user_id in result.scalars().all()]
        await redis_client.delete(users_key)
        if user_ids:
            await redis_client.sadd(users_key, *user_ids)  # 批量写入 Set
        
        # 统一 30 分钟 TTL,与 loaded/count 一起过期,防止幽灵状态
        await redis_client.expire(users_key, LIKE_CACHE_TTL)
        await redis_client.set(loaded_key, "1", ex=LIKE_CACHE_TTL)
        await _publish_like_warmed(target_id, target_type)
    finally:
        await redis_client.delete(lock_key)


async def _set_like_status_in_db(db: AsyncSession,
                                 user_id: int,
                                 target_id: int,
                                 target_type: str,
                                 is_liked: bool,
                                 *,
                                 commit: bool = True) -> bool:
    """
    ## 将点赞状态持久化写入db(幂等db写入)
    所谓幂等性:对同一个请求,重复执行多次操作,产生同样的结果
    - 若 已经点赞 -> 幂等返回 
    - 若 未点赞 -> 幂等写入 db

    Args:
        db: 数据库会话
        user_id: 用户 ID
        target_id: 目标对象 ID
        target_type: 目标类型（"article" 或 "comment"）
        is_liked: 目标点赞状态（True 表示点赞,False 表示取消点赞）
    """
    existing = await db.execute(
        select(Likes).where(
            Likes.user_id == user_id,
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
    )
    like = existing.scalar_one_or_none()
    changed = False
    if is_liked:
        if not like:
            db.add(Likes(user_id=user_id, target_id=target_id, target_type=target_type))
            await update_like_count(db, target_id, target_type, 1)
            changed = True
    else:
        if like:       
            await db.delete(like)
            await update_like_count(db, target_id, target_type, -1)
            changed = True
    if commit and changed:
        await db.commit()
    return changed


async def _set_like_status_in_db_with_count(db: AsyncSession,
                                            user_id: int,
                                            target_id: int,
                                            target_type: str,
                                            is_liked: bool) -> tuple[int, bool]:
    """
    设置数据库中的点赞目标状态并返回当前计数。

    Args:
        db: 数据库会话。
        user_id: 当前用户 ID。
        target_id: 点赞目标 ID。
        target_type: 点赞目标类型。
        is_liked: 期望的最终点赞状态。

    Returns:
        当前点赞总数和本次操作是否改变状态。
    """
    changed = await _set_like_status_in_db(
        db, user_id, target_id, target_type, is_liked
    )
    like_count = await _get_target_like_count(db, target_id, target_type)
    return like_count, changed


async def _update_target_count(db: AsyncSession,
                             target_id: int, 
                             target_type: str, 
                             delta: int) -> None:
    """
    ## 根据 target_type 更新 对应 like_count
    """
    if target_type == "article":
        await db.execute(
            update(Article)
            .where(Article.id == target_id)
            .values(like_count=Article.like_count + delta)
        )
    elif target_type == "comment":
        await db.execute(
            update(Comment)
            .where(Comment.id == target_id)
            .values(like_count=Comment.like_count + delta)
        )

async def update_like_count(db: AsyncSession,
                            target_id: int, 
                            target_type: str, 
                            delta: int) -> None:
    """
    ## 更新点赞的统一入口
    """
    await _update_target_count(db, target_id, target_type, delta)
import itertools
_cache_stats = {"hit": 0, "miss": 0}
async def get_article_like_target(
    db: AsyncSession,
    slug: str,
) -> tuple[int, int, int] | None:
    """
    查询文章点赞链路所需的最小字段。

    Args:
        db: 数据库会话。
        slug: 已发布文章的 URL 标识。

    Returns:
        文章 ID、作者 ID、数据库点赞数；文章不存在时返回 None。
    """
    key = f"{LIKE_TARGET_CACHE_PREFIX}{slug}"
    try:
        cached = await redis_client.get(key)
    except Exception:
        cached = None  # Redis 故障 fail-open 走 db
    if cached is not None:
        _cache_stats["hit"] += 1
        return tuple(json.loads(cached))
    _cache_stats["miss"] += 1
    row = (
        await db.execute(
            select(Article.id, Article.author_id, Article.like_count).where(
                Article.slug == slug,
                Article.is_deleted == False,
                Article.is_published == True,
            )
        )
    ).one_or_none()
    if row is None:
        return None
    target = tuple(row)
    try:
        await redis_client.set(key, json.dumps(target), ex=LIKE_TARGET_CACHE_TTL)
    except Exception:
        pass
    return target


async def get_comment_like_target(
    db: AsyncSession,
    comment_id: int,
) -> tuple[int, int, int, int] | None:
    """
    查询评论点赞链路所需的最小字段。

    Args:
        db: 数据库会话。
        comment_id: 评论 ID。

    Returns:
        评论 ID、作者 ID、所属文章 ID、数据库点赞数；评论不存在时返回 None。
    """
    row = (
        await db.execute(
            select(
                Comment.id,
                Comment.author_id,
                Comment.article_id,
                Comment.like_count,
            ).where(Comment.id == comment_id)
        )
    ).one_or_none()
    return tuple(row) if row else None


async def change_like_status(db: AsyncSession,
                             user_id: int,
                             target_id: int,
                             target_type: str) -> bool:
    """
    ## 切换点赞的状态
    返回 True 表示当前是已赞状态,False 表示未赞状态
    """
    existing = await db.execute(
        select(Likes).where(
            Likes.user_id == user_id,
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
    )
    like = existing.scalar_one_or_none()

    is_liked = like is None
    await _set_like_status_in_db(db, user_id, target_id, target_type, is_liked)
    return is_liked


async def change_like_status_cached(db: AsyncSession,
                                    user_id: int,
                                    target_id: int,
                                    target_type: str,
                                    is_liked: bool) -> dict:
    """
    设置 Redis 中的点赞目标状态并返回权威计数。

    Lua 使用 SADD/SREM 设置期望状态，通过 SCARD 获取计数，仅在状态实际
    变化时写入 Redis Stream。Redis 不可用时回退数据库幂等写入。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        target_id: 目标对象 ID (文章或评论)
        target_type: 目标类型 ("article" / "comment")
        is_liked: 期望的最终点赞状态

    Returns:
        包含目标信息、最终点赞状态、点赞数和是否实际变更的字典。
    """
    users_key, _, _ = _like_keys(target_id, target_type)
    if not _redis_breaker_allows_request():
        like_count, changed = await _set_like_status_in_db_with_count(
            db, user_id, target_id, target_type, is_liked
        )
        if target_type == "article" and changed:
            await bump_article_hot_score(target_id, like_delta=1 if is_liked else -1)
        return {
            "target_id": target_id,
            "target_type": target_type,
            "like_count": like_count,
            "is_liked": is_liked,
            "changed": changed,
        }

    try:
        await _warm_like_cache(db, target_id, target_type)
        result = await redis_client.eval(
            _SET_LIKE_STATE_LUA,
            2,
            users_key,
            LIKE_STREAM,
            str(user_id),
            str(target_id),
            target_type,
            str(LIKE_STREAM_MAXLEN),
            int(is_liked),
        )
        like_count = int(result[1])
        changed = bool(int(result[2]))
    except Exception:
        _record_redis_failure()
        like_count, changed = await _set_like_status_in_db_with_count(
            db, user_id, target_id, target_type, is_liked
        )
        if target_type == "article" and changed:
            await bump_article_hot_score(target_id, like_delta=1 if is_liked else -1)
        return {
            "target_id": target_id,
            "target_type": target_type,
            "like_count": like_count,
            "is_liked": is_liked,
            "changed": changed,
        }
    _record_redis_success()
    if target_type == "article" and changed:
        await bump_article_hot_score(target_id, like_delta=1 if is_liked else -1)
    return {
        "target_id": target_id,
        "target_type": target_type,
        "like_count": like_count,
        "is_liked": is_liked,
        "changed": changed,
    }
    

async def get_like_status(db: AsyncSession,
                          user_id: int,
                          target_id: int,
                          target_type: str,
                          like_count: int) -> dict:
    """
    ## 查询目标的点赞状态
    """
    existing = await db.execute(
        select(Likes.id).where(
            Likes.user_id == user_id,
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
    )
    is_liked = existing.scalar_one_or_none() is not None
    return {
        "target_id": target_id,
        "target_type": target_type,
        "like_count": like_count,
        "is_liked": is_liked,
    }


async def get_like_status_cached(db: AsyncSession,
                                 user_id: int,
                                 target_id: int,
                                 target_type: str,
                                 like_count: int) -> dict:
    """
    优先从 Redis Set 读取点赞状态和计数，Redis 不可用时回退数据库。
    """
    users_key, _, _ = _like_keys(target_id, target_type)
    try:
        await _warm_like_cache(db, target_id, target_type)
        return {
            "target_id": target_id,
            "target_type": target_type,
            "like_count": int(await redis_client.scard(users_key)),
            "is_liked": bool(await redis_client.sismember(users_key, str(user_id))),
        }
    except Exception:
        return await get_like_status(db, user_id, target_id, target_type, like_count)

async def batch_get_like_status(db: AsyncSession,
                                user_id: int,
                                target_ids: list[int],
                                target_type: str) -> dict[int, bool]:
    """
    ## 批量查询目标的点赞状态
    返回 {target_id: True/False} 字典  
    N 个目标只需要 1 次 SQL 查询  
    """
    if not target_ids:
        return {}
    
    result = await db.execute(
        select(Likes.target_id).where(
            Likes.user_id == user_id,
            Likes.target_id.in_(target_ids),
            Likes.target_type == target_type
        )
    )
    like_ids = set(result.scalars().all())
    return {
        target_id: target_id in like_ids
        for target_id in target_ids
    }

async def get_the_likers(db: AsyncSession,
                         target_id: int,
                         target_type: str,
                         limit: int = 10) -> list[Likes]:
    """
    ## 获取目标的点赞者列表
    通用函数, 文章和评论都用同一个
    """
    result = await db.execute(
        select(Likes)
        .where(
            Likes.target_id == target_id,
            Likes.target_type == target_type
        )
        .order_by(Likes.create_at.desc())
        .limit(limit)
        )
    return list(result.scalars().all())

async def get_user_history_likes(db: AsyncSession,
                                user: int,
                                target_type: str | None = None,
                                page: int = 1,
                                per_page: int = 10) -> tuple[list[Likes], int]:
    """
    ## 查询自己的的点赞历史
    按照时间倒序, 分页返回
    主页展示"我赞过的文章"
    """

    valid_article = and_(
        Likes.target_type == "article",
        exists().where(Article.id == Likes.target_id),
    )
    valid_comment = and_(
        Likes.target_type == "comment",
        exists().where(Comment.id == Likes.target_id),
    )

    query = select(Likes).where(Likes.user_id == user)
    if target_type == "article":
        query = query.where(valid_article)
    elif target_type == "comment":
        query = query.where(valid_comment)
    else:
        query = query.where(or_(valid_article, valid_comment))
    query = query.order_by(Likes.create_at.desc())

    total = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total.scalar() or 0 # 兼容 0, 即None -> int | None

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return items, total


async def enrich_like_history_items(db: AsyncSession,
                                    items: list[Likes]) -> list[dict]:
    """
    ## 为点赞历史记录补充标题和跳转链接
    返回可直接序列化的 dict 列表
    """
    if not items:
        return []

    article_ids = [item.target_id for item in items if item.target_type == "article"]
    comment_ids = [item.target_id for item in items if item.target_type == "comment"]
    article_map = {}
    comment_map = {}

    if article_ids:
        rows = await db.execute(
            select(Article, User)
            .join(User, Article.author_id == User.id)
            .where(Article.id.in_(article_ids))
        )
        article_map = {article.id: (article, author) for article, author in rows.all()}

    if comment_ids:
        rows = await db.execute(
            select(Comment, Article, User)
            .join(Article, Comment.article_id == Article.id)
            .join(User, Comment.author_id == User.id)
            .where(Comment.id.in_(comment_ids))
        )
        comment_map = {comment.id: (comment, article, author) for comment, article, author in rows.all()}

    result = []
    for item in items:
        base = {
            "liked_at": item.create_at,
            "target_type": item.target_type,
            "target_id": item.target_id,
        }
        if item.target_type == "article":
            row = article_map.get(item.target_id)
            if not row:
                continue
            article, author = row
            author_name = author.nickname or author.username
            result.append({
                **base,
                "title": article.title,
                "url": f"/articles/{article.slug}",
                "article_title": article.title,
                "article_url": f"/articles/{article.slug}",
                "comment_content": "",
                "author_id": author.id,
                "author_name": author_name,
                "author_avatar": author.avatar,
            })
            continue

        row = comment_map.get(item.target_id)
        if not row:
            continue
        comment, article, author = row
        author_name = author.nickname or author.username
        content = "此评论已被删除" if comment.is_deleted else comment.content
        preview = content[:120] + "…" if len(content) > 120 else content
        result.append({
            **base,
            "title": preview,
            "url": f"/articles/{article.slug}#comment-{comment.id}",
            "article_title": article.title,
            "article_url": f"/articles/{article.slug}",
            "comment_content": preview,
            "author_id": author.id,
            "author_name": author_name,
            "author_avatar": author.avatar,
        })
    return result
