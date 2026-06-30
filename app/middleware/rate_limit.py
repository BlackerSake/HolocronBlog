from fastapi import Request, HTTPException
from app.core.redis import redis_client
import logging
logger = logging.getLogger(__name__)

RATE_LIMIT = 60
RATE_LIMIT_WINDOW = 60


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    client_ip = _get_client_ip(request)
    key = f"rate_limit:{client_ip}"

    count = await redis_client.incr(key)
    ttl = await redis_client.ttl(key)
    if ttl < 0:
        await redis_client.expire(key, RATE_LIMIT_WINDOW)
    if count > RATE_LIMIT:
        raise HTTPException(status_code=429, detail="访问频率过高")

    return await call_next(request)