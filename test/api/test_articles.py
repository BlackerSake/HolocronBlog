

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
async def _prepare_data(db_session, test_user):
    """预置数据：2篇已发布文章 + 1篇草稿（作者均为 testuser）"""
    from app.models.article import Article
    from app.models.tag import Tag
    from app.models.category import Category
    cat = Category(name="api-tech", description="api-tech")
    tag1 = Tag(name="python")
    tag2 = Tag(name="fastapi")
    db_session.add_all([cat, tag1, tag2])
    await db_session.commit()
    await db_session.refresh(cat)
    db_session.add_all([
        Article(title="Published One", slug="published-one",
                content="# Pub 1", content_html="<h1>Pub 1</h1>",
                summary="first pub", is_published=True,
                author_id=test_user.id, category_id=cat.id, tags=[tag1]),
        Article(title="Published Two", slug="published-two",
                content="# Pub 2", content_html="<h1>Pub 2</h1>",
                summary="second pub", is_published=True,
                author_id=test_user.id, category_id=cat.id, tags=[tag2]),
        Article(title="Draft Article", slug="draft-article",
                content="# Draft", content_html="<h1>Draft</h1>",
                summary="a draft", is_published=False,
                author_id=test_user.id),
    ])
    await db_session.commit()


class TestListArticles:
    """GET /articles — 列表查询参数传递"""

    async def test_list_published_only(self, client: AsyncClient):
        """默认只返回已发布文章，草稿不可见"""
        resp = await client.get("/articles")
        assert resp.status_code == 200
        slugs = {i["slug"] for i in resp.json()["data"]["items"]}
        assert "published-one" in slugs
        assert "draft-article" not in slugs

    async def test_list_pagination(self, client: AsyncClient):
        """分页参数生效"""
        resp = await client.get("/articles", params={"page": 1, "per_page": 1})
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["total"] == 2
        assert data["pages"] == 2

    async def test_list_filter_by_category(self, client: AsyncClient):
        """按分类筛选"""
        resp = await client.get("/articles", params={"category_id": 1})
        assert len(resp.json()["data"]["items"]) > 0

    async def test_list_search_by_title(self, client: AsyncClient):
        """按关键词搜索标题"""
        resp = await client.get("/articles", params={"search": "Published"})
        assert len(resp.json()["data"]["items"]) == 2

    async def test_list_search_no_match(self, client: AsyncClient):
        """搜不到 -> 空列表"""
        resp = await client.get("/articles", params={"search": "zzzznothing"})
        assert resp.json()["data"]["items"] == []


class TestGetArticle:
    """GET /articles/{slug} — slug 路由"""

    async def test_get_published_returns_200(self, client: AsyncClient):
        """已发布文章 -> 200"""
        with patch("app.routers.articles.redis_client") as m:
            m.incr = AsyncMock(return_value=1)
            m.get = AsyncMock(return_value="1")
            resp = await client.get("/articles/published-one")
        assert resp.status_code == 200

    async def test_get_draft_returns_404(self, client: AsyncClient):
        """草稿 -> 404"""
        resp = await client.get("/articles/draft-article")
        assert resp.status_code == 404

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        """不存在的 slug -> 404"""
        resp = await client.get("/articles/no-such-article")
        assert resp.status_code == 404


class TestCreateArticle:
    """POST /articles — 认证与校验"""

    async def test_create_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.post("/articles", json={
            "title": "Hack", "content": "x", "summary": "s",
        })
        assert resp.status_code == 401

    async def test_create_with_auth_returns_200(self, client: AsyncClient, admin_headers: dict):
        """拥有 article:create 权限的用户 -> 200"""
        resp = await client.post("/articles", json={
            "title": "New", "content": "# Hello", "summary": "s",
        }, headers=admin_headers)
        assert resp.status_code == 200

    async def test_create_missing_title_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ):
        """缺少必填字段 -> 422"""
        resp = await client.post("/articles", json={
            "content": "no title",
        }, headers=admin_headers)
        assert resp.status_code == 422


class TestUpdateArticle:
    """PUT /articles/{slug} — 认证与权限"""

    async def test_update_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.put("/articles/published-one", json={"title": "Hacked"})
        assert resp.status_code == 401

    async def test_update_by_non_author_returns_403(self, client: AsyncClient):
        """非作者 -> 403"""
        from app.core.security import create_access_token
        await client.post("/api/v1/register", json={
            "username": "otheruser", "password": "otherpass123",
        })
        headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'otheruser'})}"}
        resp = await client.put("/articles/published-one", json={
            "title": "Hacked by other",
        }, headers=headers)
        assert resp.status_code == 403

    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict
    ):
        """不存在的文章 -> 404"""
        resp = await client.put("/articles/no-such", json={
            "title": "Nope",
        }, headers=admin_headers)
        assert resp.status_code == 404


class TestUnpublishArticle:
    """PATCH /articles/{slug}/unpublish — 权限"""

    async def test_unpublish_by_admin(self, client: AsyncClient, admin_headers: dict):
        """管理员 -> 200"""
        resp = await client.patch(
            "/articles/published-one/unpublish", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["is_published"] is False

    async def test_unpublish_by_non_admin(self, client: AsyncClient, auth_headers: dict):
        """普通用户 -> 403"""
        resp = await client.patch(
            "/articles/published-two/unpublish", headers=auth_headers)
        assert resp.status_code == 403

    async def test_unpublish_already_draft(self, client: AsyncClient, admin_headers: dict):
        """已是草稿 -> 400"""
        resp = await client.patch(
            "/articles/draft-article/unpublish", headers=admin_headers)
        assert resp.status_code == 400

    async def test_unpublish_nonexistent(self, client: AsyncClient, admin_headers: dict):
        """不存在 -> 404"""
        resp = await client.patch(
            "/articles/no-such/unpublish", headers=admin_headers)
        assert resp.status_code == 404


class TestDeleteArticle:
    """DELETE /articles/{slug} — 权限"""

    async def test_delete_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.delete("/articles/published-one")
        assert resp.status_code == 401

    async def test_delete_by_author(self, client: AsyncClient, auth_headers: dict):
        """作者本人 -> 204"""
        resp = await client.delete("/articles/published-one", headers=auth_headers)
        assert resp.status_code == 204
        # 验证不再出现在公开列表
        list_resp = await client.get("/articles")
        slugs = {i["slug"] for i in list_resp.json()["data"]["items"]}
        assert "published-one" not in slugs

    async def test_delete_by_admin(self, client: AsyncClient, admin_headers: dict):
        """管理员 -> 204"""
        resp = await client.delete("/articles/published-two", headers=admin_headers)
        assert resp.status_code == 204

    async def test_delete_by_non_author_non_admin_returns_403(self, client: AsyncClient):
        """非作者非管理员 -> 403"""
        from app.core.security import create_access_token
        await client.post("/api/v1/register", json={
            "username": "stranger", "password": "stranger123",
        })
        headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'stranger'})}"}
        resp = await client.delete("/articles/published-one", headers=headers)
        assert resp.status_code == 403

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        """不存在 -> 404"""
        resp = await client.delete("/articles/no-such", headers=auth_headers)
        assert resp.status_code == 404


class TestBackendList:
    """GET /articles/backend/list — 后台列表权限"""

    async def test_requires_auth(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.get("/articles/backend/list")
        assert resp.status_code == 401

    async def test_author_sees_own_drafts(self, client: AsyncClient, auth_headers: dict):
        """作者看到自己的全部文章（含草稿）"""
        resp = await client.get("/articles/backend/list", headers=auth_headers)
        slugs = {i["slug"] for i in resp.json()["data"]["items"]}
        assert "draft-article" in slugs

    async def test_admin_sees_all_published(self, client: AsyncClient, admin_headers: dict):
        """管理员看到所有已发布文章"""
        resp = await client.get("/articles/backend/list", headers=admin_headers)
        assert len(resp.json()["data"]["items"]) >= 2


class TestBackendDetail:
    """GET /articles/backend/detail/{slug}"""

    async def test_nonexistent_returns_404(self, client: AsyncClient):
        """不存在 -> 404"""
        resp = await client.get("/articles/backend/detail/no-such")
        assert resp.status_code == 404

    async def test_returns_article(self, client: AsyncClient, published_article):
        """正常返回文章详情（无需认证）"""
        resp = await client.get(f"/articles/backend/detail/{published_article.slug}")
        assert resp.status_code == 200
        assert resp.json()["data"]["slug"] == published_article.slug


class TestArticleViews:
    """GET /articles/{slug} — Redis 浏览量降级"""

    async def test_view_incremented(self, client: AsyncClient):
        """访问文章触发 redis incr，并返回 views 值"""
        with patch("app.routers.articles.redis_client") as mock_r:
            mock_r.incr = AsyncMock(return_value=5)
            mock_r.get = AsyncMock(return_value="5")
            with patch("app.services.article_cache_service.redis_client") as cache_r:
                cache_r.get = AsyncMock(return_value=None)
                cache_r.set = AsyncMock(retirn_value=True)
                cache_r.deleta = AsyncMock()
                resp = await client.get("/articles/published-one")
        assert resp.status_code == 200
        assert resp.json()["data"]["views"] == 5
        mock_r.incr.assert_awaited_once_with("article:views:published-one")


class TestHotArticles:
    """GET /articles/hot — 热门文章缓存行为"""

    @pytest.fixture(autouse=True)
    async def _hot_article(self, db_session, test_user):
        from app.models.article import Article
        db_session.add(Article(
            title="Hot Article", slug="hot-article",
            content="# Hot", content_html="<h1>Hot</h1>",
            summary="top article", is_published=True,
            author_id=test_user.id, views=100,
        ))
        await db_session.commit()

    async def test_cache_miss_queries_db(self, client: AsyncClient):
        """redis 无缓存 -> 查 DB"""
        with patch("app.services.ranking_service.redis_client") as m:
            m.get = AsyncMock(return_value=None)
            m.zrevrange = AsyncMock(return_value=[])
            m.set = AsyncMock()
            m.zadd = AsyncMock()
            resp = await client.get("/articles/hot")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) > 0

    async def test_cache_hit_returns_cached(self, client: AsyncClient):
        """redis 有缓存 -> 直接返回"""
        cached = '[{"id":99,"title":"cached","slug":"cached","summary":"s","is_published":true,"created_at":"2026-01-01T00:00:00Z","updated_at":null,"author":{"id":1,"username":"testuser","role":"user","email":"testuser@example.com","is_active":true,"created_at":"2026-01-01T00:00:00Z"},"category":null,"tags":[],"cover_image":null}]'
        with patch("app.services.ranking_service.redis_client") as m:
            m.get = AsyncMock(return_value=cached)
            resp = await client.get("/articles/hot")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["title"] == "cached"

    async def test_no_auth_required(self, client: AsyncClient):
        """不需要认证"""
        with patch("app.services.ranking_service.redis_client") as m:
            m.get = AsyncMock(return_value=None)
            m.zrevrange = AsyncMock(return_value=[])
            m.set = AsyncMock()
            m.zadd = AsyncMock()
            resp = await client.get("/articles/hot")
        assert resp.status_code == 200
