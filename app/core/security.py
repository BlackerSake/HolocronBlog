from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings
import unicodedata
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def verify_password(
        plain_password: str,
        hashed_password: str) -> bool:
    """使用现有 哈希值 验证密码"""
    plain_password = unicodedata.normalize("NFC", plain_password)
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码的哈希"""
    if password == "":
        raise ValueError("密码不能为空")
    
    # NFC 规范,统一编码
    password = unicodedata.normalize("NFC", password)
    
    password_bytes = password.encode("utf-8")
    if len(password_bytes) < 8:
        raise ValueError("密码长度不能小于 8 个字符")
    if len(password_bytes) > 72:
        raise ValueError("密码长度不能大于 72 个字符")
    
    return pwd_context.hash(password)

def create_access_token(
        data: dict,
        expires_delta: timedelta | None = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy() # 创建要编码的数据
    if expires_delta: # 创建过期时间
        expire = datetime.now(settings.tz) + expires_delta

    else:
        expire = datetime.now(settings.tz) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES # 默认过期时间 300s
            )
    to_encode.update({"exp": expire}) # 更新数据
    encoded_jwt = jwt.encode(
        to_encode, # 要编码的数据
        settings.SECRET_KEY, # 密钥
        algorithm="HS256",
    )
    return encoded_jwt


def create_refresh_token(username: str) -> str:
    """创建 JWT 刷新令牌，有效期更长"""
    expire = datetime.now(settings.tz) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": username, "purpose": "refresh", "exp": expire},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


