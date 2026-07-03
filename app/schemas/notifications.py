from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserOut


class NotificationCreate(BaseModel):
    """信息创建参数"""
    initiator_id: int
    recipient_id: int
    type: str = Field(max_length=64)
    article_id: int | None = None
    comment_id: int | None = None
    content: str = Field(max_length=1024)
    preview: str | None = Field(None, max_length=256)

    model_config = ConfigDict(from_attributes=True)


class NotificationListItem(BaseModel):
    """信息列表项 响应详情"""
    id: int
    type: str
    initiator_id: int
    content: str
    article_id: int | None
    article_slug: str | None = None
    comment_id: int | None
    preview: str | None
    is_read: bool
    created_at: datetime
    initiator: UserOut | None

    model_config = ConfigDict(from_attributes=True)


class UnreadNotificationCount(BaseModel):
    """未读信息数量"""
    count: int
    model_config = ConfigDict(from_attributes=True)
