

import asyncio
from contextlib import suppress
import random

from httpx import delete
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.schemas.article import ArticleOut
from app.services.article_service import get_published_article_by_slug

ARTICLE_CACHE_PREFIX = "cache:article:detail"
ARTICLE_CACHE_LOCK_PREFIX = "lock:cache:article:detail"
ARTICLE_CACHE_NULL = "__NULL__"

ARTICLE_DETAIL_CACHE_TTL = 60 * 10
ARTICLE_DETAIL_CACHE_JITTER = 60
ARTICLE_NULL_CACHE_TTL = 30
ARTICLE_CACHE_LOCK_TTL = 5
ARTICLE_CACHE_WAIT_SECONDS = 1.0

def _article_detail_cache_key(slug: str) -> str:
    """文章详情缓存key"""
    return f"{ARTICLE_CACHE_PREFIX}:{slug}"

def _article_detail_lock_key(slug: str) -> str:
    """文章详情缓存重建互斥锁 key"""
    return f"{ARTICLE_CACHE_LOCK_PREFIX}:{slug}"

def _article_cache_ttl() -> int:
    """TTL 随机打散,避免同类key 同时过期造成缓存雪崩"""
    return ARTICLE_DETAIL_CACHE_TTL + random.randint(0, ARTICLE_DETAIL_CACHE_JITTER)

async def get_cached_article(slug: str) -> tuple[bool, ArticleOut | None]:
    """
    读取文章的详情缓存,返回是否命中缓存, 缓存数据

    Returns:
        (hit, article data)
    """
    cached = await redis_client.get(_article_detail_cache_key(slug))
    # 缓存未命中
    if cached is None:
        return False, None
    # 缓存命中, 但数据为空
    if cached == ARTICLE_CACHE_NULL:
        return True, None
    try:
        return True, ArticleOut.model_validate_json(cached)
    except ValidationError:
        # 缓存数据格式错误, 删除缓存
        await redis_client.delete(_article_detail_cache_key(slug))
        return False, None

async def set_article_cache(slug: str, article: ArticleOut | None) -> ArticleOut | None:
    """写入文章详情缓存; None使用短TTL空值缓存防穿透"""
    cache_key = _article_detail_cache_key(slug)
    if article is None:
        await redis_client.set(cache_key, ARTICLE_CACHE_NULL, ex=ARTICLE_NULL_CACHE_TTL)
        return None
    
    data = ArticleOut.model_validate(article) # 缓存文章详细
    await redis_client.set(cache_key, data.model_dump_json(), ex=_article_cache_ttl())

async def rebuild_article_cache(db: AsyncSession, slug: str) -> ArticleOut | None:
    """从db重建文章详情缓存"""
    article = await get_published_article_by_slug(db, slug)
    data = ArticleOut.model_validate(article) if article else None
    await set_article_cache(slug, data)
    return data
async def get_public_article_cached(db: AsyncSession, slug: str) -> ArticleOut | None:
    """
    读取公开文章的详情缓存
    
    Cache-Aside模式:
    - 命中正常缓存: 直接返回ArticleOut
    - 命中空值缓存: 直接返回None, 防缓存穿透
    - 未命中: 通过 SET NX EX 互斥重建缓存, 防缓存击穿
    - redis 异常: fail-open 降级处理,回退db
    """
    try:
        # 命中情况与缓存数据
        hit, data = await get_cached_article(slug)
        if hit:
            return data
        
        lock_key = _article_detail_lock_key(slug)
        locked = await redis_client.set(lock_key, "1", nx=True, ex=ARTICLE_CACHE_LOCK_TTL)

        if locked:
            # 缓存重建锁成功: 尝试读取缓存
            try:
                hit, data = await get_cached_article(slug)
                if hit:
                    return data
                return await rebuild_article_cache(db, slug)
            finally:
                await redis_client.delete(lock_key)
        waited = 0.0
        while waited < ARTICLE_CACHE_WAIT_SECONDS:
            await asyncio.sleep(0.05)
            waited += 0.05
            hit, data = await get_cached_article(slug)
            if hit:
                return data
        
        # NOTE await 后直接查询db,若缓存击穿明显,则再加入psub唤醒
        article = await get_published_article_by_slug(db, slug)
        return ArticleOut.model_validate(article) if article else None
    except Exception:
        article = await get_published_article_by_slug(db, slug)
        return ArticleOut.model_validate(article) if article else None

async def invalidate_article_cache(slug: str) -> None:
    """主动失效文章详情缓存及依赖的热门文章缓存"""
    with suppress(Exception):
        await redis_client.delete(
            _article_detail_cache_key(slug),
            _article_detail_lock_key(slug),
            "hot_articles"
        )

async def rebuild_article_cache_batch(db: AsyncSession, slugs: list[str]) -> int:
    """后台批量重建文章缓存, 用于缓存持久化恢复后的 warm-up"""
    rebuilt = 0
    for slug in slugs:
        article = await rebuild_article_cache(db, slug)
        if article:
            rebuilt += 1
    return rebuilt