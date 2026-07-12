import pytest

from app.services.article_cache_service import(
    ARTICLE_CACHE_NULL,
    _article_detail_cache_key,
    get_public_article_cached,
    invalidate_article_cache,
)


class FakeRedis:
    def __init__(self):
        self.data = {}
    
    async def get(self, key):
        return self.data.get(key)
    async def set(self, key, value, nx=False, ex=None):
        # 当 nx 与 key 不存在时，才设置 key 的值
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True
    async def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
        return len(keys)

@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.services.article_cache_service.redis_client", fake)
    return fake

async def test_cache_miss_loads_article(db_session, published_article, fake_redis):
    """缓存未命中时 查db并写入文章详情缓存"""
    article = await get_public_article_cached(db_session, published_article.slug)

    assert article is not None
    assert article.slug == published_article.slug
    assert _article_detail_cache_key(published_article.slug) in fake_redis.data

async def test_null_cache_for_missing_article(db_session, fake_redis):
    """文章不存在 写入短ttl空值缓存,防缓存穿透"""
    article = await get_public_article_cached(db_session, "not-found")

    assert article is None
    assert fake_redis.data[_article_detail_cache_key("not-found")] == ARTICLE_CACHE_NULL

async def test_cache_hit_skips_db(db_session, published_article, fake_redis):
    """命中文章详情缓存时 返回缓存数据"""
    first = await get_public_article_cached(db_session, published_article.slug)
    second = await get_public_article_cached(db_session, published_article.slug)

    assert first is not None
    assert second is not None
    assert first.slug == published_article.slug
    assert second.slug == published_article.slug

async def test_invalidate_article_cache(fake_redis):
    """主动失效文章详情缓存 互斥锁 和热门文章缓存"""
    fake_redis.data["cache:article:detail:a"] = "cached"
    fake_redis.data["lock:cache:article:detail:a"] = "1"
    fake_redis.data["hot_articles"] = "[]"

    await invalidate_article_cache("a")
    assert "cache:article:detail:a" not in fake_redis.data
    assert "lock:cache:article:detail:a" not in fake_redis.data
    assert "hot_articles" not in fake_redis.data