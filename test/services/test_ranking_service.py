




from app.models.article import Article
from app.services.ranking_service import ARTICLE_HOT_RANK_KEY, bump_article_hot_score, get_hot_article_from_rank


async def test_bump_article_hot_score_updates_zset(mock_redis):
    """浏览/点赞事件进入 redis zset 热榜索引"""
    await bump_article_hot_score(42, view_delta=2, like_delta=1)

    assert mock_redis.zsets[ARTICLE_HOT_RANK_KEY]["42"] == 7.0

async def test_get_hot_articles_from_rank_preserves_zset_order(
        db_session,
        test_user,
        category,
        mock_redis
):
    """热榜按照zset分数倒序返回 db负责获取文章数据"""
    low = Article(
        title="Low",
        slug="low",
        content="# Low",
        content_html="<h1>Low</h1>",
        summary="low",
        is_published=True,
        author_id=test_user.id,
        category_id=category.id,
        views=1,
    )
    high = Article(
        title="High",
        slug="high",
        content="# High",
        content_html="<h1>High</h1>",
        summary="high",
        is_published=True,
        author_id=test_user.id,
        category_id=category.id,
        views=100,
        )
    db_session.add_all([low,high])
    await db_session.commit()
    await db_session.refresh(low)
    await db_session.refresh(high)

    await mock_redis.zadd(ARTICLE_HOT_RANK_KEY,{str(low.id):1, str(high.id):100})
    items = await get_hot_article_from_rank(db_session, limit=2)
    assert [item.slug for item in items] == ["high", "low"] 
    