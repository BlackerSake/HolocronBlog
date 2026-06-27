"""速率限制中间件测试（本地内存降级路径，redis 不可用时自动 fallback）"""
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.middleware.rate_limit import _get_client_ip, _loacl_rate_limit


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


class TestLocalRateLimit:
    """本地内存限流（redis 异常时降级使用）"""

    def test_under_limit_passes(self):
        """60 次以内不限流"""
        for _ in range(59):
            assert _loacl_rate_limit("test-ip-1") is False

    def test_exceed_limit_blocks(self):
        """超过 60 次限流"""
        for _ in range(60):
            _loacl_rate_limit("test-ip-2")
        assert _loacl_rate_limit("test-ip-2") is True

    def test_different_ip_not_affected(self):
        """不同 IP 独立计数"""
        for _ in range(60):
            _loacl_rate_limit("busy-ip")
        assert _loacl_rate_limit("other-ip") is False


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
        resp = await client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_multiple_requests_pass(self, client: AsyncClient):
        """低于限额的多次请求正常通过"""
        for _ in range(5):
            resp = await client.get("/ping")
            assert resp.status_code == 200
