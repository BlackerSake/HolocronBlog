from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from datetime import datetime

# 注册时,用户需要提交的参数
class UserCreate(BaseModel):
    username: str
    email: EmailStr | None = None
    password: str

# 返回给前端时的数据 (隐藏密码)
class UserOut(BaseModel):
    id: int
    username: str
    role: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True # Pydantic v2 写法，代替 orm_mode
class UserProfileUpdate(BaseModel):
    nickname: str | None = None
    avatar: str | None = None
    bio: str | None = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
            if len(value) > 50:
                raise ValueError('昵称长度不能超过50个字符')
        return value
    @field_validator("avatar")
    @classmethod
    def validate_avator(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
            if not value.startswith(("http://", "https://")):
                raise ValueError("头像地址必须是有效URL")
        return value

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
            if len(value) > 255:
                raise ValueError('简介长度不能超过255个字符')
        return value

class UserProfileOut(BaseModel):
    id: int
    username: str
    nickname: str | None
    avatar: str | None
    bio: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)