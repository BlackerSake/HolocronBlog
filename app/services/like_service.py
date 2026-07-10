import asyncio
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

logger = logging.getLogger(__name__)

#  Lua 脚本原子完成: Set 切换 + Count 更新 + XADD 写入 Stream
# 三次 Redis 操作在同一 EVAL 内完成,消除 dual-write 不一致窗口
_TOGGLE_LIKE_LUA = """
local liked = redis.call("SISMEMBER", KEYS[1], ARGV[1])
local is_liked
local count
if liked == 1 then
    redis.call("SREM", KEYS[1], ARGV[1])
    count = tonumber(redis.call("GET", KEYS[2]) or "0") - 1
    if count < 0 then count = 0 end
    is_liked = 0
else
    redis.call("SADD", KEYS[1], ARGV[1])
    count = tonumber(redis.call("GET", KEYS[2]) or "0") + 1
    is_liked = 1
end

redis.call("SET", KEYS[2], count)
local event_id = redis.call(
    "XADD", KEYS[3], "MAXLEN", "~", ARGV[4], "*",
    "user_id", ARGV[1],
    "target_id", ARGV[2],
    "target_type", ARGV[3],
    "is_liked", is_liked
)
return {is_liked, count, event_id}
"""

LIKE_CACHE_TTL = 60 * 30              # 缓存 TTL: 30 分钟,统一过期防止幽灵状态
LIKE_INIT_LOCK_TTL = 5               # 预热分布式锁超时: 5 秒,防止死锁
LIKE_INIT_WAIT_TIMES = 5             # 自旋等待次数
LIKE_INIT_WAIT_SECONDS = 0.02        # 单次自旋间隔 (20ms)
LIKE_REDIS_BREAKER_THRESHOLD = 5     # 连续 5 次 Redis 失败 → 熔断打开
LIKE_REDIS_BREAKER_RESET_SECONDS = 30  # 熔断后 30 秒进入半开状态,放行探测请求

_redis_failure_count = 0
_redis_breaker_opened_at = 0.0


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


def _like_keys(target_id: int, target_type: str) -> tuple[str, str, str, str]:
    """生成点赞功能使用的 Redis 键名元组

    Args:
        target_id: 目标对象 ID（文章或评论）
        target_type: 目标类型（"article" 或 "comment"）

    Returns:
        (用户集合键, 计数字键, 已加载标记键, 初始化锁键) 四元组
    """
    base = f"like:{target_type}:{target_id}"
    return (
        f"{base}:users",
        f"{base}:count",
        f"{base}:loaded",
        f"{base}:init_lock",
    )


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
    ### 分布式做 + 自旋等待
    - 第一个拿到锁的请求去 查db 并写入缓存
    - 其他请求自旋等待,等锁释放后直接读取缓存
    - 自旋超时未就绪则抛出 LikeCacheWarmupError,调用方降级到 DB 路径
    - 缓存 TTL: LIKE_CACHE_TTL (30 分钟),loaded / count / users 统一过期
    Args:
        db: 数据库会话
        target_id: 目标对象 ID
        target_type: 目标类型（"article" 或 "comment"）
    """
    users_key, count_key, loaded_key, lock_key = _like_keys(target_id, target_type)
    if await redis_client.exists(loaded_key):
        return

    locked = await redis_client.set(lock_key, "1", nx=True, ex=LIKE_INIT_LOCK_TTL)
    # 抢锁, 若失败则短暂自旋等待,避免缓存击穿
    # NX:只有键不存在时才设置成功. 用以保证互斥
    # EX: 锁过期时间 LIKE_INIT_LOCK_TTL 秒,防止死锁. 二者结合保证进程崩了,锁自动释放,
    if not locked:
        # 没抢到锁,即锁其他进程抢占. 短暂自旋等待,等待其他进程预热完  

        for _ in range(LIKE_INIT_WAIT_TIMES):
            await asyncio.sleep(LIKE_INIT_WAIT_SECONDS)
            if await redis_client.exists(loaded_key):
                return
        # 还没预热完毕,抛出异常让上层降级到 DB 路径
        raise LikeCacheWarmupError(f"like cache warm-up timeout: {target_type}:{target_id}")
    """
    TODO 缓存预热
    可以升级为redis分布式锁 + 双重锁检查: 自旋退出之前再做一次existing检查
    还可以不做自旋,自旋会在asyncio里阻塞事件循环,虽然有sleep让出,但是盲等可优化
    故引入**本地缓存 + Redis Pub/Sub缓存失效广播**:对于每个worker维护一个asyncio.Event
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
        await redis_client.set(count_key, len(user_ids), ex=LIKE_CACHE_TTL)    # 计数
        await redis_client.set(loaded_key, "1", ex=LIKE_CACHE_TTL)     # 标记已加载
    finally:
        await redis_client.delete(lock_key)


async def _set_like_status_in_db(db: AsyncSession,
                                 user_id: int,
                                 target_id: int,
                                 target_type: str,
                                 is_liked: bool,
                                 *,
                                 commit: bool = True) -> None:
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


async def _change_like_status_in_db_with_count(db: AsyncSession,
                                               user_id: int,
                                               target_id: int,
                                               target_type: str) -> tuple[bool, int]:
    """DB fallback 路径：切换点赞状态并返回 DB 中的当前计数"""
    is_liked = await change_like_status(db, user_id, target_id, target_type)
    like_count = await _get_target_like_count(db, target_id, target_type)
    return is_liked, like_count


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

async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Comment:
    """
    ## 根据 ID 查询评论
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise ValueError(f"Comment with id {comment_id} not found")
    return comment

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
                                    target_type: str) -> dict:
    """
    ## Redis 原子切换点赞状态,接口实时返回 Redis 计数

    ### 流程说明:
    1. 熔断器检查: OPEN 态直接走 DB fallback,不碰 Redis
    2. 缓存预热: `_warm_like_cache` 确保 like set + count 已就绪 (懒加载)
    3. Lua 脚本原子执行:
       - `SISMEMBER` 判断当前状态
       - `SADD`/`SREM` 切换用户集合
       - `SET` 更新计数
       - `XADD` 追加事件到 Redis Stream
       — 以上四次操作在同一次 EVAL 内完成,消除 dual-write 不一致窗口
    4. DB 持久化由 Stream consumer 异步批量落库,不阻塞当前请求

    ### 异常路径:
    - Lua/Redis 异常 → `_record_redis_failure()` 累计熔断计数 → DB fallback
    - 连续 LIKE_REDIS_BREAKER_THRESHOLD 次失败 → 熔断打开
    - LIKE_REDIS_BREAKER_RESET_SECONDS 后放行探测请求,成功则关闭熔断

    ### Args:
        db: 数据库会话
        user_id: 当前用户 ID
        target_id: 目标对象 ID (文章或评论)
        target_type: 目标类型 ("article" / "comment")

    ### Returns:
        dict: {target_id, target_type, like_count, is_liked}
    """
    users_key, count_key, _, _ = _like_keys(target_id, target_type)
    if not _redis_breaker_allows_request():
        is_liked, like_count = await _change_like_status_in_db_with_count(
            db, user_id, target_id, target_type
        )
        return {
            "target_id": target_id,
            "target_type": target_type,
            "like_count": like_count,
            "is_liked": is_liked,
        }

    try:
        # 确保 缓存已经预热加载
        await _warm_like_cache(db, target_id, target_type)
        # 使用Lua脚本 原子切换点赞状态并返回最新计数
        result = await redis_client.eval(
            _TOGGLE_LIKE_LUA,
            3,
            users_key,
            count_key,
            LIKE_STREAM,
            str(user_id),
            str(target_id),
            target_type,
            str(LIKE_STREAM_MAXLEN),
        )
        is_liked = bool(int(result[0]))
        like_count = int(result[1])
    except Exception:
        _record_redis_failure()
        is_liked, like_count = await _change_like_status_in_db_with_count(
            db, user_id, target_id, target_type
        )
        return {
            "target_id": target_id,
            "target_type": target_type,
            "like_count": like_count,
            "is_liked": is_liked,
        }
    _record_redis_success()

    return {
        "target_id": target_id,
        "target_type": target_type,
        "like_count": like_count,
        "is_liked": is_liked,
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
    优先从 Redis Set/String 读取点赞状态,Redis 不可用时回退 DB
    """
    users_key, count_key, _, _ = _like_keys(target_id, target_type)
    try:
        await _warm_like_cache(db, target_id, target_type)
        cached_count = await redis_client.get(count_key)
        return {
            "target_id": target_id,
            "target_type": target_type,
            "like_count": int(cached_count if cached_count is not None else like_count),
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
