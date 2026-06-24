from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def verify_password(
        plain_password: str,
        hashed_password: str,
) -> bool:
    """使用现有 哈希值 验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码的哈希"""
    return pwd_context.hash(password)

def create_access_token(
        data: dict, 
        expires_delta: timedelta | None = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy() # 创建要编码的数据
    if expires_delta: # 创建过期时间
        expire = datetime.now(timezone.utc) + expires_delta
    
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES # 默认过期时间 300s
            ) 
        to_encode.update({"exp": expire}) # 更新数据
        encoded_jwt = jwt.encode(
            to_encode, # 要编码的数据
            settings.SECRET_KEY, # 密钥
            algorithm=settings.ALGORITHM, # 加密算法 
        )
        return encoded_jwt


