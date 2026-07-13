



import json
import logging
import random

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.article import Article
from app.core import redis_client
from app.schemas.article import ArticleListItem

logger = logging.getLogger(__name__)

ARTICLE_HOT_RANK_KEY = "rank:article:hot"
ARTICLE_HOT_CACHE_KEY = "cache:articles:hot"

ARTICLE_HOT_CACHE_TTL = 60
ARTICLE_HOT_CACHE_JITTER = 30

ARTICLE_VIEW_SCORE = 1
ARTICLE_LIKE_SCORE = 5

def _hot_cache_ttl() -> int:
    """热门榜列表缓存 TTL. 打散,避免榜单缓存雪崩(同一时间批量过期)"""
    return ARTICLE_HOT_CACHE_TTL + random.randint(0,ARTICLE_HOT_CACHE_JITTER)

def _article_hot_score(article: Article) -> float:
    """
    ## 计算文章热度分数

    views: 低权重行为  
    like: 高权重行为 
    """
    return float((article.views or 0) * ARTICLE_VIEW_SCORE 
                 + (article.like_count or 0) * ARTICLE_LIKE_SCORE)

async def bump_article_hot_score(article_id: int,
                                 *,
                                 view_delta: int = 0,
                                 like_delta: int = 0) -> None:
    """
    ## 增量更新文章热度榜

    设计点:  
    - Redis ZSet 的 ZINCRBY 做原子累加,天然适合排行榜
    - 只更新排序索引, 不删除榜单列表缓存; 缓存TTL很短,允许秒级延迟
    - Redis 异常时 fail-open,不影响主业务链路
    """
    score_delta = view_delta * ARTICLE_VIEW_SCORE + like_delta * ARTICLE_LIKE_SCORE
    if score_delta == 0:
        return 
    try:
        await redis_client.zincrby(ARTICLE_HOT_RANK_KEY, 
                                   score_delta,
                                   str(article_id))
    except Exception:
        logger.exception("更新文章热榜 ZSet 失败, article_id=%s",article_id)

async def remove_article_from_hot_rank(article_id: int) -> None:
    """
    ## 从热榜中移除文章 
    删除排序索引后, 同时删除热门榜列表缓存,防止用户在短时间里看到已经下线的文章
    """
    try:
        await redis_client.zrem(ARTICLE_HOT_RANK_KEY, str(article_id))
        await redis_client.delete(ARTICLE_HOT_CACHE_KEY)
    except Exception:
        logger.exception("移除文章热榜索引失败 article_id=%s",article_id)

async def _load_article_by_ids_preserve_order(db: AsyncSession, article_ids: list[int]) -> list[ArticleListItem]:
    """按照 ZSet 排名顺序从db回溯文章, 并过滤已删除/未发布文章"""
    if not article_ids:
        return []
    
    articles = await db.execute(
        select(Article).where(
            Article.id.in_(article_ids),
            Article.is_published == True,
            Article.is_deleted == False
        )
        .options(
            selectinload(Article.author),
            selectinload(Article.category),
            selectinload(Article.tags)
        )
    )
    article_map = {
        article.id: ArticleListItem.model_validate(article)
        for article in articles.scalars().all()
    }
    return [article_map[article_id] for article_id in article_ids if article_id in article_map]

async def _load_hot_articles_from_db(db: AsyncSession, limit: int) -> list[ArticleListItem]:
    """Redis 热榜不可用或者未预热的时候 回退db排序"""
    articles = await db.execute(
        select(Article)
        .where(
            Article.is_published == True,
            Article.is_deleted == False
        )
        .order_by(
            Article.views.desc(),
            Article.like_count.desc(),
            Article.created_at.desc()
        )
        .limit(limit)
        .options(
            selectinload(Article.author),
            selectinload(Article.category),
            selectinload(Article.tags)
        )
    )
    articles = list(articles.scalars().all())
    
    try:
        if articles:
            await redis_client.zadd(ARTICLE_HOT_RANK_KEY,
                                    {str(article.id): _article_hot_score(article)
                                     for article in articles}
                                     )
    except Exception:
        logger.exception("DB 溯源后回灌文章热榜 ZSet 失败")
    return [ArticleListItem.model_validate(article) for article in articles]

async def get_hot_article_from_rank(db: AsyncSession,
                                    *,
                                    limit: int = 10) -> list[ArticleListItem]:
    """
    ## 获取文章热门排行榜
    ### 读取链路:
    1. 短TTL Json缓存:保护热门榜接口本身,避免每次都db溯源
    2. Redis ZSet: 使用 ZREVRANGE 取热度最高的 article_id
    3. db 溯源: Redis 未命中,按照views/like_count 查询,并回灌ZSet  
    
    拆开了"排序索引"和"文章详情":
    - ZSet 负责高频排序
    - db 负责完整数据和发布状态 过滤
    """
    try:
        cached = await redis_client.get(ARTICLE_HOT_CACHE_KEY)
        if cached:
            return [ArticleListItem.model_validate(item) 
                    for item in json.loads(cached)]
        
        raw_ids: list[str] = await redis_client.zrevrange(ARTICLE_HOT_RANK_KEY, 0, limit - 1)  # type: ignore[assignment]
        article_ids = [int(item) for item in raw_ids]
        
        items = await _load_article_by_ids_preserve_order(db, article_ids)
        if not items:
            items = await _load_hot_articles_from_db(db, limit)
        await redis_client.set(ARTICLE_HOT_CACHE_KEY,
                               json.dumps([item.model_dump(mode="json")
                                           for item in items]),
                                           ex=_hot_cache_ttl())
        return items
    except (ValueError, TypeError, ValidationError, json.JSONDecodeError):
        await redis_client.delete(ARTICLE_HOT_CACHE_KEY)
        return await _load_hot_articles_from_db(db, limit)
    except Exception:
        logger.exception("读取文章缓存热榜失败,降级 db排序")
        return await _load_hot_articles_from_db(db, limit)
    
async def rebuild_hot_article_rank(db: AsyncSession,
                                   *,
                                   limit: int = 1000) -> int:
    """后台重建热榜 zset, 用于redis重启, aof恢复后或定时对账后的索引修复"""
    articles = await db.execute(
        select(Article)
        .where(
            Article.is_published == True,
            Article.is_deleted == False
        )
        .order_by(
            Article.views.desc(),
            Article.like_count.desc()
        )
        .limit(limit)
    )
    articles = list(articles.scalars().all())

    try:
        await redis_client.delete(ARTICLE_HOT_RANK_KEY, ARTICLE_HOT_CACHE_KEY)
        if articles:
            await redis_client.zadd(
                ARTICLE_HOT_RANK_KEY,
                {str(article.id): _article_hot_score(article)
                 for article in articles}
            )
    except Exception:
        logger.exception("重建文章热榜 zset 失败")
        return 0
    return len(articles)
