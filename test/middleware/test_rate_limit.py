"""速率限制中间件测试"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.middleware.rate_limit import _get_client_ip, _get_token_bucket

class TestClientIp:
    """IP 提取逻辑"""

    def test_x_forwarded_for(self):
        """X-Forwarded-For 取第一个 IP"""
        from fastapi import Request
        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.50, 10.0.0.1")],
        }
        ip = _get_client_ip(Request(scope))
        assert ip == "203.0.113.50"

    def test_x_real_ip(self):
        """无 X-Forwarded-For 时取 X-Real-IP"""
        from fastapi import Request
        scope = {
            "type": "http",
            "headers": [(b"x-real-ip", b"10.0.0.1")],
        }
        ip = _get_client_ip(Request(scope))
        assert ip == "10.0.0.1"

    def test_fallback_to_client_host(self):
        """都无则取 client.host"""
        from fastapi import Request
        scope = {
            "type": "http",
            "headers": [],
            "client": ("192.168.1.1", 12345),
        }
        ip = _get_client_ip(Request(scope))
        assert ip == "192.168.1.1"


class TestMiddlewarePassthrough:
    """中间件集成：正常请求不被拦截"""

    @pytest.fixture
    def app(self):
        app = FastAPI()
        from starlette.middleware.base import BaseHTTPMiddleware
        from app.middleware.rate_limit import rate_limit_middleware
        app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        return app

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_passthrough(self, client: AsyncClient):
        """正常请求返回 200"""
        with patch("app.middleware.rate_limit.redis_client") as m:
            m.eval = AsyncMock(return_value=[1, 0])
            resp = await client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_multiple_requests_pass(self, client: AsyncClient):
        """低于限额的多次请求正常通过"""
        with patch("app.middleware.rate_limit.redis_client") as m:
            m.eval = AsyncMock(return_value=[1, 0])
            for _ in range(5):
                resp = await client.get("/ping")
                assert resp.status_code == 200
    
    async def test_token_bucket_rejects(self, client: AsyncClient):
        """token butcket 不足时返回429"""
        with patch("app.middleware.rate_limit.redis_client") as m:
            m.eval = AsyncMock(return_value=[0, 2])
            resp = await client.get("/ping")
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == '2'

class TestTokenBucketConfig:
    """令牌桶配置"""
    def test_login_bucket(self):
        """登录接口的小brust"""
        assert _get_token_bucket("/api/v1/login") == (5, 5 / 60)
    
    def test_default_bucket(self):
        """其他接口的默认brust"""
        assert _get_token_bucket("/articles/a/like") == (20, 1.0)