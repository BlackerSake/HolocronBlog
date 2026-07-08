from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from datetime import datetime

# 注册时,用户需要提交的参数
class UserCreate(BaseModel):
    """用户注册参数"""
    username: str
    email: EmailStr | None = None
    password: str

# 返回给前端时的数据 (隐藏密码)
class UserOut(BaseModel):
    """用户公开信息响应"""
    id: int
    username: str
    role: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True # Pydantic v2 写法，代替 orm_mode
class UserProfileUpdate(BaseModel):
    """用户个人资料更新参数，所有字段均可选"""
    nickname: str | None = None
    avatar: str | None = None
    bio: str | None = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        """校验昵称长度不超过50个字符

        Args:
            value: 昵称字符串，可能为None

        Returns:
            去除首尾空格后的昵称，如为空或None则返回None

        Raises:
            ValueError: 昵称长度超过50个字符时抛出
        """
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
        """校验头像地址为有效URL

        Args:
            value: 头像URL字符串，可能为None

        Returns:
            去除首尾空格后的URL，如为空或None则返回None

        Raises:
            ValueError: URL不是以http://或https://开头时抛出
        """
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
        """校验个人简介长度不超过255个字符

        Args:
            value: 简介字符串，可能为None

        Returns:
            去除首尾空格后的简介，如为空或None则返回None

        Raises:
            ValueError: 简介长度超过255个字符时抛出
        """
        if value is not None:
            value = value.strip()
            if not value:
                return None
            if len(value) > 255:
                raise ValueError('简介长度不能超过255个字符')
        return value

class UserProfileOut(BaseModel):
    """用户个人资料响应模型"""
    id: int
    username: str
    nickname: str | None
    avatar: str | None
    bio: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)