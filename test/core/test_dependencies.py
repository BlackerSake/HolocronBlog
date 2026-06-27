"""依赖注入测试：get_current_user / get_current_admin_user

通过 /users/me 和 受 admin 保护的端点 间接验证。
"""
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


class TestGetCurrentUser:
    """get_current_user 依赖测试（通过 /users/me）"""

    async def test_valid_token_returns_user(self, client: AsyncClient, auth_headers: dict):
        """有效 token -> 200 + 用户信息"""
        resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "testuser"

    async def test_no_token_returns_401(self, client: AsyncClient):
        """无 token -> 401"""
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        """无效 token -> 401"""
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_expired_token_returns_401(self, client: AsyncClient):
        """过期 token -> 401"""
        from datetime import timedelta
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1),  # 立即过期
        )
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_disabled_user_returns_403(
        self, client: AsyncClient, db_session
    ):
        """已禁用用户 -> 403  
        需要先创建一个禁用用户"""
        from app.models.user import User
        from sqlalchemy import select
        user = User(
            username="testuser",
            password="testpassword",
            email="",
            is_active=False,
        )
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(
            select(User).where(User.username == "testuser")
        )
        user = result.scalar_one()
        user.is_active = False
        await db_session.commit()

        token = create_access_token(data={"sub": "testuser"})
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestGetCurrentAdminUser:
    """get_current_admin_user 依赖测试"""

    async def test_admin_token_allowed(
        self, client: AsyncClient, admin_headers: dict
    ):
        """管理员 token -> 正常访问"""
        resp = await client.get("/api/v1/users/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "admin"

    async def test_user_token_forbidden(
        self, client: AsyncClient, auth_headers: dict, db_session
    ):
        """普通用户 token 访问管理接口 -> 403"""
        from app.core.dependencies import get_current_admin_user
        from app.models.user import User
        from sqlalchemy import select
        from app.schemas.common import Response

        resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 200
