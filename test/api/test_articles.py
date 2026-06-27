"""文章 API 集成测试：列表 / 详情 / 创建 / 更新 / 删除 / 取消发布 / 浏览量 / 热门"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
async def _prepare_data(db_session, test_user):
    """预置数据：2篇已发布文章 + 1篇草稿（作者均为 testuser）"""
    from app.models.article import Article
    from app.models.tag import Tag
    from app.models.category import Category

    author = test_user

    cat = Category(name="tech", description="tech category")
    tag1 = Tag(name="python")
    tag2 = Tag(name="fastapi")
    db_session.add_all([cat, tag1, tag2])
    await db_session.commit()
    await db_session.refresh(cat)
    await db_session.refresh(tag1)
    await db_session.refresh(tag2)

    articles_data = [
        Article(
            title="Published One",
            slug="published-one",
            content="# Pub 1",
            content_html="<h1>Pub 1</h1>",
            summary="first pub",
            is_published=True,
            author_id=author.id,
            category_id=cat.id,
            tags=[tag1],
        ),
        Article(
            title="Published Two",
            slug="published-two",
            content="# Pub 2",
            content_html="<h1>Pub 2</h1>",
            summary="second pub",
            is_published=True,
            author_id=author.id,
            category_id=cat.id,
            tags=[tag2],
        ),
        Article(
            title="Draft Article",
            slug="draft-article",
            content="# Draft",
            content_html="<h1>Draft</h1>",
            summary="a draft",
            is_published=False,
            author_id=author.id,
        ),
    ]
    db_session.add_all(articles_data)
    await db_session.commit()


class TestListArticles:
    """GET /articles"""

    URL = "/articles"

    async def test_list_published_only(self, client: AsyncClient):
        """默认只返回已发布的文章"""
        resp = await client.get(self.URL)
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 2
        slugs = {i["slug"] for i in items}
        assert "published-one" in slugs
        assert "draft-article" not in slugs

    async def test_list_pagination(self, client: AsyncClient):
        """分页参数生效"""
        resp = await client.get(self.URL, params={"page": 1, "per_page": 1})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["total"] == 2
        assert data["pages"] == 2

    async def test_list_filter_by_category(self, client: AsyncClient):
        """按分类筛选"""
        resp = await client.get(self.URL, params={"category_id": 1})
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) > 0

    async def test_list_search_by_title(self, client: AsyncClient):
        """按关键词搜索标题"""
        resp = await client.get(self.URL, params={"search": "Published"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 2

    async def test_list_search_by_content(self, client: AsyncClient):
        """按关键词搜索内容"""
        resp = await client.get(self.URL, params={"search": "Pub 1"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 1

    async def test_list_empty_result(self, client: AsyncClient):
        """搜不到 -> 空列表"""
        resp = await client.get(self.URL, params={"search": "zzzznothing"})
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []


class TestGetArticle:
    """GET /articles/{slug}"""

    async def test_get_published(self, client: AsyncClient):
        """已发布文章 -> 200 + 完整详情"""
        resp = await client.get("/articles/published-one")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "Published One"
        assert data["author"]["username"] == "testuser"

    async def test_get_published_has_author_category_tags(
        self, client: AsyncClient
    ):
        """文章详情包含 author / category / tags 关联数据"""
        resp = await client.get("/articles/published-one")
        data = resp.json()["data"]
        assert data["author"] is not None
        assert data["category"] is not None
        assert len(data["tags"]) > 0

    async def test_get_draft_returns_404(self, client: AsyncClient):
        """草稿返回 404"""
        resp = await client.get("/articles/draft-article")
        assert resp.status_code == 404

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        """不存在的 slug -> 404"""
        resp = await client.get("/articles/no-such-article")
        assert resp.status_code == 404


class TestCreateArticle:
    """POST /articles"""

    URL = "/articles"

    async def test_create_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.post(self.URL, json={
            "title": "Hack", "content": "x", "summary": "s",
        })
        assert resp.status_code == 401

    async def test_create_success(self, client: AsyncClient, auth_headers: dict):
        """认证用户 -> 201 + 文章信息"""
        resp = await client.post(self.URL, json={
            "title": "New Article",
            "content": "# Hello",
            "summary": "a summary",
            "is_published": False,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "New Article"
        assert data["slug"] == "new-article"
        assert data["is_published"] is False
        assert data["author"]["username"] == "testuser"

    async def test_create_with_category_and_tags(
        self, client: AsyncClient, auth_headers: dict
    ):
        """指定分类和标签 -> 关联正确"""
        resp = await client.post(self.URL, json={
            "title": "Tagged Article",
            "content": "content",
            "summary": "tagged summary",
            "category_id": 1,
            "tags_id": [1, 2],
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["category"] is not None
        assert len(data["tags"]) == 2

    async def test_create_missing_title_fails(
        self, client: AsyncClient, auth_headers: dict
    ):
        """缺少必填字段 title -> 422"""
        resp = await client.post(self.URL, json={
            "content": "no title",
        }, headers=auth_headers)
        assert resp.status_code == 422


class TestUpdateArticle:
    """PUT /articles/{slug}"""

    async def test_update_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.put("/articles/published-one", json={"title": "Hacked"})
        assert resp.status_code == 401

    async def test_update_title_by_author(
        self, client: AsyncClient, auth_headers: dict
    ):
        """作者本人 -> 200 + slug重新生成"""
        resp = await client.put("/articles/published-one", json={
            "title": "Updated Title",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "Updated Title"
        assert data["slug"] == "updated-title"

    async def test_update_content_rerenders_html(
        self, client: AsyncClient, auth_headers: dict
    ):
        """修改内容 -> content_html 同步更新"""
        resp = await client.put("/articles/published-one", json={
            "content": "# New Heading",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "<h1>New Heading</h1>" in resp.json()["data"]["content_html"]

    async def test_update_by_non_author_returns_403(
        self, client: AsyncClient
    ):
        """非作者更新 -> 403
        注册另一个用户 进行测试"""
        from app.core.security import create_access_token
        from httpx import AsyncClient
        await client.post("/api/v1/register", json={
            "username": "otheruser",
            "password": "otherpass123",
        })
        other_token = create_access_token(data={"sub": "otheruser"})
        headers = {"Authorization": f"Bearer {other_token}"}
        resp = await client.put("/articles/published-one", json={
            "title": "Hacked by other",
        }, headers=headers)
        assert resp.status_code == 403

    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        """不存在的文章 -> 404"""
        resp = await client.put("/articles/no-such-article", json={
            "title": "Nope",
        }, headers=auth_headers)
        assert resp.status_code == 404

    async def test_publish_article(
        self, client: AsyncClient, auth_headers: dict
    ):
        """将草稿发布 -> is_published=True"""
        resp = await client.put("/articles/draft-article", json={
            "is_published": True,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["is_published"] is True


class TestUnpublishArticle:
    """PATCH /articles/{slug}/unpublish"""

    async def test_unpublish_by_admin(
        self, client: AsyncClient, admin_headers: dict
    ):
        """管理员取消发布 -> 200"""
        resp = await client.patch(
            "/articles/published-one/unpublish", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_published"] is False

    async def test_unpublish_by_non_admin(
        self, client: AsyncClient, auth_headers: dict
    ):
        """普通用户 -> 403"""
        resp = await client.patch(
            "/articles/published-two/unpublish", headers=auth_headers,
        )
        assert resp.status_code == 403

    async def test_unpublish_already_draft(
        self, client: AsyncClient, admin_headers: dict
    ):
        """已经是草稿 -> 400"""
        resp = await client.patch(
            "/articles/draft-article/unpublish", headers=admin_headers,
        )
        assert resp.status_code == 400

    async def test_unpublish_nonexistent(
        self, client: AsyncClient, admin_headers: dict
    ):
        """不存在 -> 404"""
        resp = await client.patch(
            "/articles/no-such/unpublish", headers=admin_headers,
        )
        assert resp.status_code == 404


class TestDeleteArticle:
    """DELETE /articles/{slug}"""

    async def test_delete_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.delete("/articles/published-one")
        assert resp.status_code == 401

    async def test_delete_by_author(
        self, client: AsyncClient, auth_headers: dict
    ):
        """作者本人 -> 204 软删除"""
        resp = await client.delete(
            "/articles/published-one", headers=auth_headers,
        )
        assert resp.status_code == 204
        # 验证不再出现在列表中
        list_resp = await client.get("/articles")
        slugs = {i["slug"] for i in list_resp.json()["data"]["items"]}
        assert "published-one" not in slugs

    async def test_delete_by_admin(
        self, client: AsyncClient, admin_headers: dict
    ):
        """管理员 -> 204"""
        resp = await client.delete(
            "/articles/published-two", headers=admin_headers,
        )
        assert resp.status_code == 204

    async def test_delete_by_non_author_non_admin_returns_403(
        self, client: AsyncClient
    ):
        """非作者非管理员 -> 403"""
        from app.core.security import create_access_token
        await client.post("/api/v1/register", json={
            "username": "stranger",
            "password": "stranger123",
        })
        token = create_access_token(data={"sub": "stranger"})
        resp = await client.delete(
            "/articles/published-one",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        """不存在 -> 404"""
        resp = await client.delete(
            "/articles/no-such-article", headers=auth_headers,
        )
        assert resp.status_code == 404


class TestBackendList:
    """GET /articles/backend/list"""

    URL = "/articles/backend/list"

    async def test_backend_list_requires_auth(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.get(self.URL)
        assert resp.status_code == 401

    async def test_author_sees_own_articles(
        self, client: AsyncClient, auth_headers: dict
    ):
        """作者看到自己的全部文章（含草稿）"""
        resp = await client.get(self.URL, headers=auth_headers)
        assert resp.status_code == 200
        slugs = {i["slug"] for i in resp.json()["data"]["items"]}
        assert "draft-article" in slugs  # 草稿可见
        assert len(slugs) >= 1

    async def test_admin_sees_all_published_and_own(
        self, client: AsyncClient, admin_headers: dict
    ):
        """管理员看到所有已发布 + 自己的文章"""
        resp = await client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        # 管理员自己没有文章，但看到所有已发布的
        assert len(resp.json()["data"]["items"]) >= 2


class TestBackendDetail:
    """GET /articles/backend/detail/{slug}"""

    async def test_backend_detail_requires_auth(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.get("/articles/backend/detail/published-one")
        assert resp.status_code == 401

    async def test_backend_detail_sees_draft(
        self, client: AsyncClient, auth_headers: dict
    ):
        """作者本人后端可见草稿"""
        resp = await client.get(
            "/articles/backend/detail/draft-article", headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["is_published"] is False

    async def test_backend_detail_nonexistent(
        self, client: AsyncClient, auth_headers: dict
    ):
        """不存在 -> 404"""
        resp = await client.get(
            "/articles/backend/detail/no-such", headers=auth_headers,
        )
        assert resp.status_code == 404


class TestArticleViews:
    """GET /articles/{slug} 浏览量（redis incr + 回写）"""

    async def test_view_incremented(
        self, client: AsyncClient
    ):
        """访问文章触发 redis incr，views 字段返回当前值"""
        with patch("app.routers.articles.redis_client") as mock_redis:
            mock_redis.incr = AsyncMock(return_value=5)
            mock_redis.get = AsyncMock(return_value="5")

            resp = await client.get("/articles/published-one")

        assert resp.status_code == 200
        assert resp.json()["data"]["views"] == 5
        mock_redis.incr.assert_awaited_once_with("article:views:published-one")


class TestHotArticles:
    """GET /articles/hot"""

    @pytest.fixture(autouse=True)
    async def _hot_article(self, db_session, test_user):
        """hot 测试专用：创建一条高浏览量已发布文章"""
        from app.models.article import Article
        article = Article(
            title="Hot Article",
            slug="hot-article",
            content="# Hot",
            content_html="<h1>Hot</h1>",
            summary="top article",
            is_published=True,
            author_id=test_user.id,
            views=100,
        )
        db_session.add(article)
        await db_session.commit()

    async def test_hot_returns_list_when_cache_miss(
        self, client: AsyncClient
    ):
        """redis 无缓存 -> 查询 DB 返回热门文章"""
        with patch("app.routers.articles.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)

            resp = await client.get("/articles/hot")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_hot_returns_cached_when_cache_hit(
        self, client: AsyncClient
    ):
        """redis 有缓存 -> 直接返回缓存"""
        cached = '[{"id":99,"title":"cached","slug":"cached","summary":"s","is_published":true,"created_at":"2026-01-01T00:00:00Z","updated_at":null,"author":{"id":1,"username":"testuser","role":"user","email":"testuser@example.com","is_active":true,"created_at":"2026-01-01T00:00:00Z"},"category":null,"tags":[],"cover_image":null}]'
        with patch("app.routers.articles.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=cached)

            resp = await client.get("/articles/hot")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["title"] == "cached"

    async def test_hot_requires_no_auth(self, client: AsyncClient):
        """不需要认证"""
        with patch("app.routers.articles.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)

            resp = await client.get("/articles/hot")

        assert resp.status_code == 200
