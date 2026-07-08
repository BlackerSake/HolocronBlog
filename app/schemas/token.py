from pydantic import BaseModel

class Token(BaseModel):
    """令牌响应模型"""
    access_token: str
    token_type: str

class TokenRefreshRequest(BaseModel):
    """令牌刷新请求参数"""
    refresh_token: str