
import pytest
from httpx import AsyncClient


async def flush_like_stream(mock_redis, db_session):
    """测试辅助：模拟后台 consumer 将 fake Redis Stream 批量落库。"""
    from app.core.like_stream import LIKE_STREAM, _flush_to_db

    messages = list(mock_redis.streams.get(LIKE_STREAM, []))
    if not messages:
        return
    await _flush_to_db(messages, db_session)
    mock_redis.streams[LIKE_STREAM] = []


class TestToggleLike:
    """POST /articles/{slug}/like"""

    async def test_without_auth_returns_401(self, client: AsyncClient, published_article):
        """未认证 -> 401"""
        resp = await client.post(f"/articles/{published_article.slug}/like")
        assert resp.status_code == 401

    async def test_like_article(self, client: AsyncClient, auth_headers, published_article):
        """点赞成功 -> 200, is_liked=True"""
        resp = await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_type"] == "article"
        assert data["target_id"] == published_article.id
        assert data["is_liked"] is True
        assert data["like_count"] == 1

    async def test_unlike_article(self, client: AsyncClient, auth_headers, published_article):
        """取消点赞 -> is_liked=False"""
        await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        resp = await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_liked"] is False
        assert resp.json()["like_count"] == 0

    async def test_like_twice_same_user(self, client: AsyncClient, auth_headers, published_article):
        """同一用户两次点赞 = 取消点赞"""
        resp1 = await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        assert resp1.json()["is_liked"] is True
        resp2 = await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        assert resp2.json()["is_liked"] is False

    async def test_multiple_users(
        self, client: AsyncClient, auth_headers, published_article, other_user,
        db_session,
    ):
        """不同用户各自点赞 -> like_count 累加"""
        from app.core.security import create_access_token
        other_token = create_access_token(data={"sub": other_user.username})
        other_headers = {"Authorization": f"Bearer {other_token}"}

        await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        resp = await client.post(
            f"/articles/{published_article.slug}/like",
            headers=other_headers,
        )
        assert resp.json()["is_liked"] is True
        assert resp.json()["like_count"] == 2
        from app.services.notification_service import get_unread_notifications_count
        assert await get_unread_notifications_count(db_session, published_article.author_id) == 1


class TestLikeStatus:
    """GET /articles/{slug}/like-status"""

    async def test_without_auth_returns_401(self, client: AsyncClient, published_article):
        """未认证 -> 401"""
        resp = await client.get(f"/articles/{published_article.slug}/like-status")
        assert resp.status_code == 401

    async def test_not_liked(self, client: AsyncClient, auth_headers, published_article):
        """未点赞 -> is_liked=False, like_count=0"""
        resp = await client.get(
            f"/articles/{published_article.slug}/like-status",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_type"] == "article"
        assert data["target_id"] == published_article.id
        assert data["is_liked"] is False
        assert data["like_count"] == 0

    async def test_shows_liked_after_like(self, client: AsyncClient, auth_headers, published_article):
        """点赞后查询 -> is_liked=True"""
        await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        resp = await client.get(
            f"/articles/{published_article.slug}/like-status",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_liked"] is True
        assert resp.json()["like_count"] == 1

    async def test_user_specific_status(self, client: AsyncClient, auth_headers, published_article, other_user):
        """用户A点赞后，用户B查不到"""
        from app.core.security import create_access_token
        other_token = create_access_token(data={"sub": other_user.username})
        other_headers = {"Authorization": f"Bearer {other_token}"}

        await client.post(
            f"/articles/{published_article.slug}/like",
            headers=auth_headers,
        )
        resp = await client.get(
            f"/articles/{published_article.slug}/like-status",
            headers=other_headers,
        )
        assert resp.json()["is_liked"] is False
        assert resp.json()["like_count"] == 1


class TestMeLikeHistory:
    """GET /me/like-history"""

    async def test_without_auth_returns_401(self, client: AsyncClient):
        """未认证 -> 401"""
        resp = await client.get("/me/like-history", params={"target_type": "article"})
        assert resp.status_code == 401

    async def test_empty_history(self, client: AsyncClient, auth_headers):
        """没有点赞 -> 空列表"""
        resp = await client.get(
            "/me/like-history", params={"target_type": "article"}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_history(self, client: AsyncClient, auth_headers, published_article, mock_redis, db_session):
        """点赞事件消费后历史记录可见"""
        await client.post(
            f"/articles/{published_article.slug}/like", headers=auth_headers,
        )
        await flush_like_stream(mock_redis, db_session)
        resp = await client.get(
            "/me/like-history", params={"target_type": "article"}, headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["target_id"] == published_article.id
        assert data[0]["target_type"] == "article"
        assert data[0]["title"] == published_article.title
        assert data[0]["url"] == f"/articles/{published_article.slug}"
        assert "liked_at" in data[0]

    async def test_filter_by_target_type(self, client: AsyncClient, auth_headers, published_article):
        """按类型过滤 -> 只返回对应类型的记录"""
        await client.post(
            f"/articles/{published_article.slug}/like", headers=auth_headers,
        )
        resp = await client.get(
            "/me/like-history", params={"target_type": "comment"}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_comment_history_details(self, client: AsyncClient, auth_headers, published_article, existing_comment, test_user, mock_redis, db_session):
        """评论点赞历史包含评论内容、原文章和作者信息"""
        await client.post(
            f"/comments/{existing_comment.id}/like", headers=auth_headers,
        )
        await flush_like_stream(mock_redis, db_session)
        resp = await client.get(
            "/me/like-history", params={"target_type": "comment"}, headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["target_type"] == "comment"
        assert data[0]["target_id"] == existing_comment.id
        assert data[0]["comment_content"] == existing_comment.content
        assert data[0]["article_title"] == published_article.title
        assert data[0]["article_url"] == f"/articles/{published_article.slug}"
        assert data[0]["url"] == f"/articles/{published_article.slug}#comment-{existing_comment.id}"
        assert data[0]["author_id"] == test_user.id
        assert data[0]["author_name"] == "test"

    async def test_returns_mixed_history_without_type(self, client: AsyncClient, auth_headers, published_article, existing_comment, mock_redis, db_session):
        """不传 target_type -> 返回文章和评论混合历史"""
        await client.post(
            f"/articles/{published_article.slug}/like", headers=auth_headers,
        )
        await client.post(
            f"/comments/{existing_comment.id}/like", headers=auth_headers,
        )
        await flush_like_stream(mock_redis, db_session)
        resp = await client.get(
            "/me/like-history", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert {item["target_type"] for item in data} == {"article", "comment"}

    async def test_history_skips_missing_targets(self, client: AsyncClient, auth_headers, db_session, published_article, test_user, mock_redis):
        """孤儿点赞记录不应生成空白假历史"""
        from app.models.like import Likes

        db_session.add(Likes(user_id=test_user.id, target_type="article", target_id=999999))
        await db_session.commit()
        await client.post(
            f"/articles/{published_article.slug}/like", headers=auth_headers,
        )
        await flush_like_stream(mock_redis, db_session)

        resp = await client.get("/me/like-history", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["target_id"] == published_article.id
        assert data[0]["title"] == published_article.title

    async def test_pagination(self, client: AsyncClient, auth_headers, published_article, db_session, test_user, category, mock_redis):
        """分页参数生效"""
        from app.models.article import Article
        a2 = Article(
            title="Second Published", slug="second-published",
            content="# 2", content_html="<p>2</p>",
            summary="second", is_published=True,
            author_id=test_user.id, category_id=category.id,
        )
        db_session.add(a2)
        await db_session.commit()
        await db_session.refresh(a2)

        for article in [published_article, a2]:
            await client.post(
                f"/articles/{article.slug}/like", headers=auth_headers,
            )
        await flush_like_stream(mock_redis, db_session)
        resp = await client.get(
            "/me/like-history",
            params={"target_type": "article", "page": 1, "per_page": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestUsersLikeHistory:
    """GET /users/{user_id}/like-history"""

    async def test_empty_history(self, client: AsyncClient, test_user):
        """没有点赞 -> 空列表"""
        resp = await client.get(
            f"/users/{test_user.id}/like-history", params={"target_type": "article"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_users_history(self, client: AsyncClient, auth_headers, published_article, test_user, other_user, mock_redis, db_session):
        """查看其他用户的点赞历史"""
        from app.core.security import create_access_token
        other_token = create_access_token(data={"sub": other_user.username})
        other_headers = {"Authorization": f"Bearer {other_token}"}

        await client.post(
            f"/articles/{published_article.slug}/like", headers=other_headers,
        )
        await flush_like_stream(mock_redis, db_session)
        resp = await client.get(
            f"/users/{other_user.id}/like-history",
            params={"target_type": "article"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["target_id"] == published_article.id
        assert data[0]["title"] == published_article.title
        assert data[0]["url"] == f"/articles/{published_article.slug}"

    async def test_does_not_require_auth(self, client: AsyncClient, test_user):
        """不需要认证"""
        resp = await client.get(
            f"/users/{test_user.id}/like-history", params={"target_type": "article"},
        )
        assert resp.status_code == 200

    async def test_filter_by_type(self, client: AsyncClient, auth_headers, published_article, test_user):
        """按类型过滤"""
        await client.post(
            f"/articles/{published_article.slug}/like", headers=auth_headers,
        )
        resp = await client.get(
            f"/users/{test_user.id}/like-history",
            params={"target_type": "comment"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
