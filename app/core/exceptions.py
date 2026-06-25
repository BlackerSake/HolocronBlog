from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
from app.schemas.common import ErrorResponse

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理 FastAPI/Starlette 的 HTTPException（401/403/404等）"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.status_code,
            message=str(exc.detail),
            detail=None
        ).model_dump()
    )

async def validation_error_handler(request: Request, exc: RequestValidationError):
    """处理 Pydantic 请求参数校验错误（422）"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            code=422,
            message="Request validation failed",
            detail=str(exc.errors())
        ).model_dump()
    )

async def global_exception_handler(request: Request, exc: Exception):
    """处理未被上述处理器捕获的异常（500）"""
    # 生产环境最好记日志
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code=500,
            message="Internal server error",
            detail=str(exc)
        ).model_dump()
    )

def register_exception_handlers(app: FastAPI):
    """在 app 实例上注册所有异常处理器"""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, global_exception_handler)