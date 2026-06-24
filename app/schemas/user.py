from pydantic import BaseModel, EmailStr
from datetime import datetime

# 注册时,用户需要提交的参数
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

# 返回给前端时的数据 (隐藏密码)
class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True # Pydantic v2 写法，代替 orm_mode