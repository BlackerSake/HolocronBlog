from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CategoryBase(BaseModel):
    """分类基础字段"""
    name: str
    description: str | None = None

class CategoryCreate(CategoryBase):
    pass # 继承CategoryBase

class CategoryUpdate(BaseModel):
    """分类更新参数，所有字段均可选"""
    name: str | None = None
    description: str | None = None

class CategoryOut(CategoryBase):
    """分类响应模型"""
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)