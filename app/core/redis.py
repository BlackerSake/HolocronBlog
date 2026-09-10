
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
    将 Redis 中缓存的文章浏览量同步回数据库。

    使用 SCAN 命令遍历所有 article:views:* 键，将当前浏览量写回对应文章的
    views 字段并提交事务。

    Args:
        db: 异步数据库会话，用于执行更新操作。
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
    后台循环任务，定期将 Redis 中的浏览量同步到数据库。

    按 REDIS_SYNC_INTERVAL 配置的间隔执行同步，支持优雅取消。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    #engine = create_async_engine(settings.DATABASE_URL)
    from app.core.database import create_engine
    engine = create_engine()
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
    """创建并启动后台浏览量同步任务。"""
    global _background_task
    _background_task = asyncio.create_task(_sync_loop())

async def stop_sync_task():
    """停止后台浏览量同步任务并关闭 Redis 连接。"""
    global _background_task

    if _background_task:
        _background_task.cancel()

        try:
            await _background_task
        except asyncio.CancelledError:
            pass
    await redis_client.close()