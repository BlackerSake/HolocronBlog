


from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LikeUserBrief(BaseModel):
    """点赞者 的简要信息"""

    id: int
    username: str
    nickname: str | None
    avatar: str | None 
    
    model_config = ConfigDict(from_attributes=True)

class LikeOut(BaseModel):
    """点赞记录"""
    user: LikeUserBrief
    target_type: str
    target_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LikeStatusOut(BaseModel):
    """点赞状态"""
    target_type: str
    target_id: int
    like_count: int
    is_liked: bool

class LikeHistoryOut(BaseModel):
    """点赞记录（含前端展示信息）"""
    liked_at: datetime
    target_type: str
    target_id: int
    title: str
    url: str
    article_title: str
    article_url: str
    comment_content: str
    author_id: int | None = None
    author_name: str
    author_avatar: str | None = None

    model_config = ConfigDict(from_attributes=True)
