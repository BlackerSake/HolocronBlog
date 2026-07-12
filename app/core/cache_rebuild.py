
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.article import Article
from app.services.article_cache_service import rebuild_article_cache_batch
logger = logging.getLogger(__name__)

CACHE_REBUILD_INTERVAL = 60 * 10
CACHE_REBUILD_LIMIT = 100

_cache_rebuild_task: asyncio.Task | None = None


async def rebuild_hot_article_caches(db: AsyncSession) -> int:
    """
    ## 后台重建热点文章详情缓存
    Redis 开启AOF后可降低数据丢失风险, 但Redis重启,缓存淘汰,手动清理后 仍然需要后台warm-up能力恢复热点缓存
    """

    rows = await db.execute(
        select(Article.slug)
        .where(
            Article.is_published == True,
            Article.is_deleted == False,
        )
        .order_by(Article.view_count.desc(), Article.like_count.desc())
        .limit(CACHE_REBUILD_LIMIT)
    )
    slugs = list(rows.scalars().all())
    return await rebuild_article_cache_batch(db, slugs)

async def _cache_rebuild_loop() -> None:
    """定期重建热点文章缓存"""
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        while True:
            await asyncio.sleep(CACHE_REBUILD_INTERVAL)
            async with session_factory() as db:
                rebuilt = await rebuild_hot_article_caches(db)
                logger.info(f"重建缓存成功，共重建 {rebuilt} 条记录")
    except asyncio.CancelledError:
        logger.info("重建缓存任务已取消")
    finally:
        # 释放数据库连接
        await engine.dispose()

async def start_cache_rebuild_task() -> None:
    """
    启动缓存重建任务
    """
    global _cache_rebuild_task
    if _cache_rebuild_task and not _cache_rebuild_task.done():
        return
    _cache_rebuild_task = asyncio.create_task(_cache_rebuild_loop())

async def stop_cache_rebuild_task() -> None:
    """
    停止缓存重建任务
    """
    global _cache_rebuild_task
    if not _cache_rebuild_task:
        return
    _cache_rebuild_task.cancel()
    try:
        await _cache_rebuild_task
    except asyncio.CancelledError:
        pass
    _cache_rebuild_task = None