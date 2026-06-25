from typing import Generic, TypeVar
from pydantic import BaseModel

DataT = TypeVar("DataT")

class Paginated(BaseModel, Generic[DataT]):
    """通用分页模型"""
    items: list[DataT]
    total: int
    page: int
    per_page: int
    pages: int
