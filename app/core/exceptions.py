from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.schemas.common import ErrorResponse
import logging

logger = logging.getLogger(__name__)


def _response(code: int, message: str, detail: str | None = None) -> JSONResponse:
    """构造统一格式的错误 JSON 响应。"""
    return JSONResponse(status_code=code, content=ErrorResponse(code=code, message=message, detail=detail).model_dump())


async def http_handler(request: Request, exc: StarletteHTTPException):
    """处理 Starlette HTTP 异常，记录警告日志并返回统一错误响应。"""
    logger.warning("%s %s → %s", request.method, request.url.path, exc.detail)
    return _response(exc.status_code, str(exc.detail))


async def validation_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误，返回 422 及详细的错误信息。"""
    return _response(422, "Request validation failed", detail=str(exc.errors()))


async def fallback_handler(request: Request, exc: Exception):
    """全局未捕获异常处理器，记录错误栈并返回 500 响应。"""
    logger.exception("%s %s → %s", request.method, request.url.path, exc)
    return _response(500, "Internal server error")


def register_exception_handlers(app: FastAPI):
    """
    向 FastAPI 应用注册统一异常处理器。

    注册 HTTP 异常、请求验证异常和全局未捕获异常三种处理器。

    Args:
        app: FastAPI 应用实例。
    """
    app.add_exception_handler(StarletteHTTPException, http_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(Exception, fallback_handler)