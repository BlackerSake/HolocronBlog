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
    """
    验证明文密码与哈希值是否匹配。

    Args:
        plain_password: 明文密码。
        hashed_password: 已存储的 bcrypt 哈希值。

    Returns:
        bool: 密码匹配返回 True，否则返回 False。
    """
    plain_password = unicodedata.normalize("NFC", plain_password)
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    生成密码的 bcrypt 哈希值，并进行编码和长度校验。

    Args:
        password: 明文密码，将经过 NFC 规范化处理。

    Returns:
        str: bcrypt 哈希字符串。

    Raises:
        ValueError: 密码为空、长度小于 8 或大于 72 字节时抛出。
    """
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
    """
    创建 JWT 访问令牌。

    Args:
        data: 要编码到令牌中的载荷数据。
        expires_delta: 可选的自定义过期时间，未指定时使用配置默认值。

    Returns:
        str: 编码后的 JWT 令牌字符串。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta

    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return encoded_jwt


def create_refresh_token(username: str) -> str:
    """
    创建 JWT 刷新令牌，有效期较长用于无感续期。

    Args:
        username: 用户名，将作为令牌的 sub 声明。

    Returns:
        str: 编码后的刷新令牌字符串。
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": username, "purpose": "refresh", "exp": expire},
        settings.SECRET_KEY,
        algorithm="HS256",
    )

