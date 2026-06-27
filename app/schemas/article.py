from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserOut
from app.schemas.category import CategoryOut
from app.schemas.tag import TagOut

class ArticleCreate(BaseModel):
    """文章创建参数"""
    title: str
    content: str
    category_id: int | None = None
    tags_id: list[int] | None = None
    summary: str | None = None
    cover_image: str | None = None
    is_published: bool = False # 默认为草稿,不发布

class ArticleUpdate(BaseModel):
    """所有字段均可选"""
    title: str | None = None
    content: str | None = None
    category_id: int | None = None
    tags_id: list[int] | None = None
    summary: str | None = None
    cover_image: str | None = None
    is_published: bool | None = None

class ArticleOut(BaseModel):
    """文章响应详情,输出的必要字段, 即数据库模型的所有必要字段"""
    id: int
    title: str
    slug: str
    content: str
    content_html: str
    summary: str | None
    cover_image: str | None
    is_published: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None
    author: UserOut
    category: CategoryOut | None
    tags: list[TagOut] = []
    views: int = 0

    model_config = ConfigDict(from_attributes=True)

class ArticleListItem(BaseModel):
    """文章列表项 响应详情"""
    id: int
    title: str
    slug: str
    summary: str | None
    cover_image: str | None
    is_published: bool
    created_at: datetime
    updated_at: datetime | None
    author: UserOut
    category: CategoryOut | None
    tags: list[TagOut] = []

    model_config = ConfigDict(from_attributes=True)