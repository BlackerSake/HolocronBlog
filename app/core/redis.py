
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.article import Article
import asyncio
import logging
logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=settings.REDIS_HOST, #default localhost
    port=settings.REDIS_PORT, #default 6379
    db=0,
    decode_responses=True,
)

# 后台任务句柄，用于关闭
_background_task: asyncio.Task | None = None

async def sync_views_from_redis_to_db(db: AsyncSession):
    """
    ## 将redis 中缓存的浏览量同步到数据库中
    """
    cursor = 0
    while True:
        # 从第一个 key 开始扫描,一次完成
        cursor, keys = await redis_client.scan(cursor, match="article:views:*",count=100)
        for key in keys:
            # 获取文章的slug
            slug = key.split(":", 2)[-1] 
            views = await redis_client.get(key)
            if views is None:
                continue
            views = int(views)
            result = await db.execute(
                select(Article).where(Article.slug == slug)
            )
            article = result.scalar_one_or_none()
            if article:
                article.views = views
        if cursor == 0:
            break
    await db.commit()

async def _sync_loop():
    """
    ## 后台循环任务
    每隔24小时将redis中的浏览量同步到数据库中
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, 
                                         expire_on_commit=False,
                                         class_=AsyncSession)

    while True:
        try:
            await asyncio.sleep(settings.REDIS_SYNC_INTERVAL)
            async with session_factory() as db:
                await sync_views_from_redis_to_db(db)
            logger.info("同步浏览量成功")
        except asyncio.CancelledError:
            logger.info("同步浏览量任务已取消")
            break
        except Exception as e:
            logger.error(f"同步浏览量任务出错: {e}")
    await engine.dispose()

async def start_sync_task():
    """
    ## 创建后台同步任务
    """
    global _background_task
    _background_task = asyncio.create_task(_sync_loop())

async def stop_sync_task():
    """
    ## 停止后台同步任务
    """
    global _background_task

    if _background_task:
        _background_task.cancel()

        try:
            await _background_task
        except asyncio.CancelledError:
            pass
    await redis_client.close()