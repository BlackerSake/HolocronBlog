from pydantic import BaseModel

class Token(BaseModel): # 创建Token, 存储访问令牌和令牌类型
    access_token: str
    token_type: str

class TokenData(BaseModel): # 创建TokenData, 存储用户名
    username: str | None = None