"""异常处理器和全局异常处理测试"""
import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient
from app.core.exceptions import register_exception_handlers

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

# 用 fixture 在测试期间临时注册，测试完自动移除
@pytest.fixture
def error_app():
    """创建一个临时 FastAPI 应用，注册异常处理器，包含触发各异常的端点"""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-error-not-exist")
    async def raise_http():
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/validation-error")
    async def raise_val():

        raise RequestValidationError(
            errors=[{"loc": ("body",), "msg": "invalid"}])

    @app.get("/server-error")
    async def raise_500():
        raise RuntimeError("internal server error")

    return app


@pytest.fixture
async def error_client(error_app):
    """
    ## 创建一个临时客户端，使用临时 FastAPI 应用
    ## NOTE 超级bug(已修复):
    raise_app_exceptions=False:  
    RuntimeError 抛出 ->  global_exception_handler 应该捕获并返回 JSONResponse  
    *然而!* ASGITransport 在中间拦截了，直接把异常重新抛出到测试层  
    导致报错: 原始 RuntimeError，不是 500 JSONResponse
    """
    transport = ASGITransport(app=error_app,
                              raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://test") as ac:
        yield ac


class TestHTTPExceptionHandler:
    """HTTPException -> JSONResponse 格式"""
    
    """
    401: 登录时用户名不存在 / 密码错误 / 账号未激活等 应该在 test_auth.py 处理
    403: 需要认证的接口不带 Token 
    """
    @pytest.mark.asyncio
    async def test_404_returns_json(self, error_client):
        """访问 不存在的 URL, 404,返回 ErrorResponse"""
        resp = await error_client.get("/http-error-not-exist")
        assert resp.status_code == 404

        body = resp.json()
        assert body["code"] == 404
        assert ("message" in body and isinstance(body["message"], str))
        assert body["detail"] == None
    
class TestValidationErrorHandler:
    """处理 Pydantic 请求参数校验错误 -> 422 JSONResponse"""
    @pytest.mark.asyncio
    async def test_422_returns_json(self, error_client):
        resp = await error_client.get("/validation-error")
        assert resp.status_code == 422

        body = resp.json()
        assert body["code"] == 422
        assert body["message"] == "Request validation failed"
        assert "invalid" in body["detail"]
        """实际返回:
        {
        "code": 422,
        "message": "Request validation failed",
        "detail": "[{'loc': ('body',), 'msg': 'invalid'}]"
        }
        """


class TestGlobalExceptionHandler:
    """处理未被其他处理器捕获的异常 -> 500 JSONResponse"""

    @pytest.mark.asyncio
    async def test_500_returns_json(self, error_client):
        
        resp = await error_client.get("/server-error")
        assert resp.status_code == 500

        body = resp.json()
        assert body["code"] == 500
        assert "message" in body and body["message"] == "Internal server error"



