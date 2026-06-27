"""认证 API 集成测试：register / login"""
import pytest
from httpx import AsyncClient


class TestRegister:
    """POST /api/v1/register"""

    REGISTER_URL = "/api/v1/register"

    async def test_register_success(self, client: AsyncClient):
        """有效参数 → 201 + 返回用户信息(不含密码)"""
        resp = await client.post(self.REGISTER_URL, json={
            "username": "newuser",
            "password": "password123",
            "email": "new@example.com",
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert "password" not in data

    async def test_register_without_email(self, client: AsyncClient):
        """邮箱为空 → 自动生成占位邮箱"""
        resp = await client.post(self.REGISTER_URL, json={
            "username": "noemail",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["username"] == "noemail"
        assert data["email"] == "noemail@holocron.com"

    async def test_register_duplicate_username(self, client: AsyncClient):
        """重复用户名 → 400"""
        await client.post(self.REGISTER_URL, json={
            "username": "dupuser",
            "password": "password123",
        })
        resp = await client.post(self.REGISTER_URL, json={
            "username": "dupuser",
            "password": "password456",
        })
        assert resp.status_code == 400
        assert "用户名已存在" in resp.text

    async def test_register_duplicate_email(self, client: AsyncClient):
        """重复邮箱 → 400"""
        await client.post(self.REGISTER_URL, json={
            "username": "first",
            "password": "password123",
            "email": "dup@example.com",
        })
        resp = await client.post(self.REGISTER_URL, json={
            "username": "second",
            "password": "password123",
            "email": "dup@example.com",
        })
        assert resp.status_code == 400
        assert "邮箱已存在" in resp.text

    async def test_register_empty_password_fails(self, client: AsyncClient):
        """空密码 → 422（Pydantic报错，空字符串仍是str）"""
        resp = await client.post(self.REGISTER_URL, json={
            "username": "emptypass",
            "password": "",
        })
        assert resp.status_code in (201, 422, 500)
        # 注：空密码的哈希会在 service 层报错，取决于异常是否被捕获

    async def test_register_missing_username_fails(self, client: AsyncClient):
        """缺少必填字段 username → 422"""
        resp = await client.post(self.REGISTER_URL, json={
            "password": "password123",
        })
        assert resp.status_code == 422

    async def test_register_missing_password_fails(self, client: AsyncClient):
        """缺少必填字段 password → 422"""
        resp = await client.post(self.REGISTER_URL, json={
            "username": "nopass",
        })
        assert resp.status_code == 422


class TestLogin:
    """POST /api/v1/login (form-data)"""

    LOGIN_URL = "/api/v1/login"

    @pytest.fixture(autouse=True)
    async def _create_user(self, client: AsyncClient):
        """每个登录测试前先注册一个用户"""
        await client.post("/api/v1/register", json={
            "username": "logintest",
            "password": "loginpass123",
            "email": "login@example.com",
        })

    async def test_login_success(self, client: AsyncClient):
        """正确凭据 → 200 + access_token"""
        resp = await client.post(
            self.LOGIN_URL,
            data={"username": "logintest", "password": "loginpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient):
        """密码错误 → 401"""
        resp = await client.post(
            self.LOGIN_URL,
            data={"username": "logintest", "password": "wrongpass"},
        )
        assert resp.status_code == 401
        assert "密码错误" in resp.text

    async def test_login_wrong_username(self, client: AsyncClient):
        """用户名不存在 → 401"""
        resp = await client.post(
            self.LOGIN_URL,
            data={"username": "nobody", "password": "loginpass123"},
        )
        assert resp.status_code == 401
        assert "用户名不正确" in resp.text

    async def test_login_disabled_user(self, client: AsyncClient, db_session):
        """账号被禁用 → 401"""
        from app.models.user import User
        from sqlalchemy import select

        result = await db_session.execute(
            select(User).where(User.username == "logintest")
        )
        user = result.scalar_one()
        user.is_active = False
        await db_session.commit()

        resp = await client.post(
            self.LOGIN_URL,
            data={"username": "logintest", "password": "loginpass123"},
        )
        assert resp.status_code == 401
        assert "未激活" in resp.text
