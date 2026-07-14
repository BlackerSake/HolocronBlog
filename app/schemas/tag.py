from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TagBase(BaseModel):
    """标签基础字段"""
    name: str

class TagCreate(TagBase):
    pass

class TagUpdate(BaseModel):
    """标签更新参数，名称可选"""
    name: str | None = None

class TagOut(TagBase):
    """标签响应模型"""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
