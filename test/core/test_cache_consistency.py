


from sqlalchemy import select

from app.core.cache_consistency import reconcile_article_view_counts, reconcile_like_counts
from app.models.article import Article


async def test_reconcile_article_view_counts_updates_db(db_session,
                                                        published_article,
                                                        mock_redis):
    """Redis 浏览量和db不一致时, 对账任务用redis实时值修复"""
    await mock_redis.set(f"article:views:{published_article.slug}",123)

    fixed = await reconcile_article_view_counts(db_session)
    await db_session.commit()

    refreshed = await db_session.scalar(
        select(Article)
        .where(Article.id == published_article.id)
    )
    assert fixed == 1
    assert refreshed.views == 123

async def test_reconcile_like_counts_updates_article_counter(db_session,
                                                             published_article,
                                                             mock_redis):
    """redis 点赞计数 与 文章冗余字段不一致时, 对账任务 修复likecount"""
    await mock_redis.set(f"like:article:{published_article.id}:count", 9)
    fixed = await reconcile_like_counts(db_session)
    await db_session.commit()
    refreshed = await db_session.scalar(
        select(Article)
        .where(Article.id == published_article.id)
    )
    assert fixed == 1
    assert refreshed.like_count == 9