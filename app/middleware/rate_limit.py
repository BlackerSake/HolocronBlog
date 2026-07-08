from fastapi import Request, HTTPException
from app.core.redis import redis_client
import logging
logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60

# 按路径前缀应用的限流规则（次数/窗口）
_PATH_LIMITS: list[tuple[str, int]] = [
    ("/api/v1/register", 3),    # 注册：3 次/分钟
    ("/api/v1/login", 5),       # 登录：5 次/分钟
]
_DEFAULT_LIMIT = 60              # 其他：60 次/分钟


def _get_client_ip(request: Request) -> str:
    """获取客户端真实IP地址

    优先从 X-Forwarded-For 头获取，其次从 X-Real-IP 头获取，
    最后回退到 request.client.host。

    Args:
        request: FastAPI 请求对象

    Returns:
        客户端IP地址字符串，无法获取时返回 "unknown"
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _get_path_limit(path: str) -> int:
    """根据请求路径获取对应的限流次数

    匹配 _PATH_LIMITS 中配置的路径前缀，
    未匹配的路径使用默认限流次数。

    Args:
        path: 请求路径字符串

    Returns:
        该路径允许的最大请求次数
    """
    for prefix, limit in _PATH_LIMITS:
        if path.startswith(prefix):
            return limit
    return _DEFAULT_LIMIT


async def rate_limit_middleware(request: Request, call_next):
    """基于Redis的IP限流中间件

    对每个请求按客户端IP和请求路径进行计数，
    超过限制时返回 429 状态码。

    Args:
        request: FastAPI 请求对象
        call_next: 下一个中间件或路由处理函数

    Returns:
        请求的响应对象

    Raises:
        HTTPException 429: 请求频率超过限制时抛出
    """
    client_ip = _get_client_ip(request)
    limit = _get_path_limit(request.url.path)
    key = f"rate_limit:{client_ip}:{request.url.path}"

    count = await redis_client.incr(key)
    ttl = await redis_client.ttl(key)
    if ttl < 0:
        await redis_client.expire(key, RATE_LIMIT_WINDOW)
    if count > limit:
        raise HTTPException(status_code=429, detail="访问频率过高")

    return await call_next(request)