


from datetime import datetime

from pydantic import BaseModel, ConfigDict


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