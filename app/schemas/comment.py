from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from datetime import datetime

from app.schemas.user import UserOut

class CommentCreate(BaseModel):
    content: str
    parent_id: int | None = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, value: str) -> str:
        value = value.strip() # 去除空格
        if not value:
            raise ValueError("内容不能为空")
        if len(value) > 2000:
            raise ValueError("内容不能超过2000字")
        return value


class CommentOut(BaseModel):
    id: int
    content: str

    author: UserOut
    parent_id: int | None

    created_at: datetime
    is_deleted: bool = False
    is_published: bool = False # 默认为编辑
    replies: list["CommentOut"] = [] # 子评论列表,自引用

    model_config = ConfigDict(from_attributes=True) # 允许从ORM模型创建

    @model_validator(mode="after")
    # model_va...在所有字段都解析完成后执行,不存在字段顺序依赖
    def mask_deleted(self) -> "CommentOut":
        """
        如果评论被删除，则将内容替换为"此评论已被删除"
        """
        if self.is_deleted:
            self.content = "此评论已被删除"
        return self
    
CommentOut.model_rebuild() # 重新构建模型
# 必须调用，解析自引用前向引用