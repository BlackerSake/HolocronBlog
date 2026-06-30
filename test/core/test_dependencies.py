"""依赖注入测试：get_current_user / get_current_admin_user

通过 /articles/backend/list（需认证）和 /categories（需 admin）验证。
"""
from datetime import timedelta
from httpx import AsyncClient
from app.core.security import create_access_token


class TestGetCurrentUser:
    """get_current_user 依赖测试（通过 /articles/backend/list）"""

    URL = "/articles/backend/list"

    async def test_valid_token_returns_200(self, client: AsyncClient, auth_headers: dict):
        """有效 token → 200"""
        resp = await client.get(self.URL, headers=auth_headers)
        assert resp.status_code == 200

    async def test_no_token_returns_401(self, client: AsyncClient):
        """无 token → 401"""
        resp = await client.get(self.URL)
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        """无效 token → 401"""
        resp = await client.get(
            self.URL,
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_expired_token_returns_401(self, client: AsyncClient):
        """过期 token → 401"""
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1),
        )
        resp = await client.get(
            self.URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_disabled_user_returns_403(self, client: AsyncClient, db_session, test_user):
        """已禁用用户 → 403"""

        test_user.is_active = False
        await db_session.commit()

        token = create_access_token(data={"sub": test_user.username})
        resp = await client.get(
            self.URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestRequirePermission:
    """require_permission 依赖测试（通过 /categories 验证）"""

    async def test_admin_token_allowed(self, client: AsyncClient, admin_headers: dict):
        """管理员 token → 正常访问"""
        resp = await client.post(
            "/categories",
            json={"name": "admin-test-cat", "description": "test"},
            headers=admin_headers,
        )
        assert resp.status_code == 201

    async def test_user_token_forbidden(self, client: AsyncClient, auth_headers: dict):
        """普通用户 token 访问管理接口 → 403"""
        resp = await client.post(
            "/categories",
            json={"name": "user-test-cat", "description": "test"},
            headers=auth_headers,
        )
        assert resp.status_code == 403
