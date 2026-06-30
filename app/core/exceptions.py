from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.schemas.common import ErrorResponse
import logging

logger = logging.getLogger(__name__)


def _response(code: int, message: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=code, content=ErrorResponse(code=code, message=message, detail=detail).model_dump())


async def http_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("%s %s → %s", request.method, request.url.path, exc.detail)
    return _response(exc.status_code, str(exc.detail))


async def validation_handler(request: Request, exc: RequestValidationError):
    return _response(422, "Request validation failed", detail=str(exc.errors()))


async def fallback_handler(request: Request, exc: Exception):
    logger.exception("%s %s → %s", request.method, request.url.path, exc)
    return _response(500, "Internal server error")


def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(StarletteHTTPException, http_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(Exception, fallback_handler)