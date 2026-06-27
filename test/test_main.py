
import pytest
from httpx import AsyncClient


class TestRoot:
    """GET /"""

    URL = "/"

    async def test_root_returns_message(self, client: AsyncClient):
        """根路径 → 200 + 欢迎消息"""
        resp = await client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["message"] == "This is my blog"

    async def test_root_content_type(self, client: AsyncClient):
        """响应 Content-Type 为 application/json"""
        resp = await client.get(self.URL)
        assert "application/json" in resp.headers["content-type"]


class TestHealth:
    """GET /health/db"""

    URL = "/health/db"

    async def test_health_returns_ok(self, client: AsyncClient):
        """数据库健康检查 → 200 + status ok"""
        resp = await client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["result"] == 1

    async def test_health_content_type(self, client: AsyncClient):
        """响应 Content-Type 为 application/json"""
        resp = await client.get(self.URL)
        assert "application/json" in resp.headers["content-type"]


class TestCORS:
    """CORS 中间件配置测试"""

    @pytest.mark.parametrize("origin", [
        "http://localhost:8848",
        "https://localhost:8848",
        "http://127.0.0.1:8848",
    ])
    async def test_allowed_origin(self, client: AsyncClient, origin: str):
        """配置的 origin → 返回 CORS 头"""
        resp = await client.get("/", headers={"Origin": origin})
        assert resp.headers.get("access-control-allow-origin") == origin

    async def test_disallowed_origin(self, client: AsyncClient):
        """未配置的 origin → 不返回 CORS 头"""
        resp = await client.get("/", headers={"Origin": "https://evil.com"})
        cors = resp.headers.get("access-control-allow-origin")
        assert cors is None or cors == "http://localhost:8848"
        # 注：FastAPI CORS 中间件默认不拒绝请求，只是不返回 ACAO 头

    async def test_cors_methods_header(self, client: AsyncClient):
        """Access-Control-Allow-Methods 为 *  
        即允许所有请求方法"""
        resp = await client.options(
            "/", headers={
                "Origin": "http://localhost:8848",
                "Access-Control-Request-Method": "GET",
            },
        )
        allowed = resp.headers.get("access-control-allow-methods","")
        # 验证已经用到的 HTTP 方法都在允许列表中
        for method in ["GET", "POST", "PUT", "DELETE","PATCH"]:
            assert method in allowed
