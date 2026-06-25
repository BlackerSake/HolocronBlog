from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel

DataT = TypeVar("DataT")

class Paginated(BaseModel, Generic[DataT]):
    """通用分页模型"""
    items: list[DataT]
    total: int
    page: int
    per_page: int
    pages: int

class Response(BaseModel, Generic[DataT]):
    """统一成功响应"""
    code: int = 200
    message: str = "success"
    data: Optional[DataT] = None

class ErrorResponse(BaseModel):
    """统一错误响应"""
    code: int
    message: str
    detail: Optional[str] = None