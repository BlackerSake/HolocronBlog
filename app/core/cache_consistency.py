


import asyncio
import logging

from sqlalchemy import func, select, update
from app.core import redis_client
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.article import Article
from app.models.comment import Comment
from app.models.like import Likes
from app.services.ranking_service import rebuild_hot_article_rank
logger = logging.getLogger(__name__)

CACHE_CONSISTENCY_INTERVAL = 60 * 5
CACHE_SCAN_COUNT = 100

_cache_consistency_task: asyncio.Task | None = None

async def _scan_keys(match: str) -> list[str]:
    """
    使用scan分批扫描redis key,避免keys 阻塞redis主线程
    """
    cursor = 0
    keys: list[str] = []

    while True:
        cursor, batch = await redis_client.scan(
            cursor,
            match=match,
            count=CACHE_SCAN_COUNT
        )
        keys.extend(batch)
        if int(cursor) == 0:
            break
    return keys

async def reconcile_article_view_counts(db: AsyncSession) -> int:
    """
    ## 对账文章浏览量

    设计策略:  
    - redis 与db不一致时, 以 redis 当前值修复db
    - 浏览量是单调递增计数, redis在架构中更接近实时值
    """
    fixed = 0
    keys = await _scan_keys("article:views:*")
    for key in keys:
        slug = key.split(":", 2)[-1]
        cached = await redis_client.get(key)
        if cached is None:
            continue

        redis_views = int(cached)
        article = await db.execute(
            select(
                Article.id,
                Article.views
            )
            .where(
                Article.slug == slug,
                Article.is_deleted == False
            )
        )
        article = article.one_or_none()
        if not article:
            continue

        article_id, db_views = article
        if int(db_views or 0) == redis_views:
            continue
        await db.execute(update(Article)
            .where(Article.id == article_id)
            .values(views=redis_views)
        )
        fixed += 1
        logger.warning("文章浏览量对账修复 slug=%s db_views=%s redis_views=%s",
                       slug, db_views, redis_views)

    return fixed

async def reconcile_like_counts(db: AsyncSession) -> int:
    """
    ## 对账点赞计数

    设计策略:  
    - 冗余字段不一致时，以 Redis Set 的成员数量修复冗余字段
    - 如果数据库明细与 Redis Set 不一致，只记录 warning；明细由 Stream
      pending 重试和死信机制追平
    """
    fixed = 0
    for target_type, model in (("article", Article), ("comment", Comment)):
        keys = await _scan_keys(f"like:{target_type}:*:loaded")

        for key in keys:
            parts = key.split(":")
            if len(parts) != 4:
                continue

            target_id = int(parts[2])
            users_key = f"like:{target_type}:{target_id}:users"
            redis_count = int(await redis_client.scard(users_key))
            db_counter = await db.scalar(
                select(model.like_count)
                .where(model.id == target_id)
            )
            if db_counter is None:
                continue

            persisted_count = await db.scalar(
                select(func.count(Likes.id))
                .where(
                    Likes.target_type == target_type,
                    Likes.target_id == target_id
                )
            )
            if int(persisted_count or 0) != redis_count:
                logger.warning("点赞明细存在一致性延迟 target_type=%s target_id=%s db_count=%s redis_count=%s",
                               target_type, target_id, persisted_count, redis_count)
            if int(db_counter or 0) == redis_count:
                continue

            await db.execute(
                update(model)
                .where(model.id == target_id)
                .values(like_count=redis_count)
            )
            fixed += 1
            logger.warning("点赞冗余计数字段对账修复 target_type=%s target_id=%s db_counter=%s redis_count=%s",
                            target_type, target_id, db_counter, redis_count)
    return fixed

async def run_cache_consistency_once(db: AsyncSession) -> dict[str, int]:
    """
    执行一次完整的缓存一致性巡检
    """
    fixed_views = await reconcile_article_view_counts(db)
    fixed_likes = await reconcile_like_counts(db)
    rebuilt_rank = await rebuild_hot_article_rank(db)

    await db.commit()

    return {
        "fixed_views": fixed_views,
        "fixed_likes": fixed_likes,
        "rebuilt_rank": rebuilt_rank,
    }

async def _cache_consistency_loop() -> None:
    """定时运行缓存一致性对账任务"""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False,class_=AsyncSession)

    try:
        while True:
            await asyncio.sleep(CACHE_CONSISTENCY_INTERVAL)
            async with session_factory() as db:
                stats = await run_cache_consistency_once(db)
                logger.info("缓存一致性对账完成 stats=%s", stats)
    except asyncio.CancelledError:
        logger.info("缓存一致性对账任务已取消")
    finally:
        await engine.dispose()

async def start_cache_consistency_task() -> None:
    """启动缓存一致性后台任务"""
    global _cache_consistency_task
    if _cache_consistency_task and not _cache_consistency_task.done():
        return 
    _cache_consistency_task = asyncio.create_task(_cache_consistency_loop())

async def stop_cache_consistency_task() -> None:
    """停止缓存一致性后台任务"""
    global _cache_consistency_task
    if not _cache_consistency_task:
        return 
    _cache_consistency_task.cancel()
    try:
        await _cache_consistency_task
    except asyncio.CancelledError:
        pass
    _cache_consistency_task = None
