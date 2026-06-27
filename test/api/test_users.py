"""用户 API 测试：GET /api/v1/users/me"""
import pytest
from httpx import AsyncClient


class TestUsersMe:
    """GET /api/v1/users/me"""

    URL = "/api/v1/users/me"

    async def test_me_with_valid_token(self, client: AsyncClient, auth_headers: dict):
        """有效 token → 返回当前用户信息"""
        resp = await client.get(self.URL, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "testuser"
        assert data["email"] == "testuser@example.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "password" not in data

    async def test_me_without_token(self, client: AsyncClient):
        """无 token → 401"""
        resp = await client.get(self.URL)
        assert resp.status_code == 401

    async def test_me_with_admin_token(self, client: AsyncClient, admin_headers: dict):
        """管理员 token → 返回管理员信息"""
        resp = await client.get(self.URL, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "adminuser"
        assert data["role"] == "admin"
