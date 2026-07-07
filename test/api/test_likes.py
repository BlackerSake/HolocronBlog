
import pytest
from httpx import AsyncClient


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

    async def test_multiple_users(self, client: AsyncClient, auth_headers, published_article, other_user):
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
