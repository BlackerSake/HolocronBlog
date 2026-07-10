import time

from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.redis import redis_client
import logging
logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_WINDOW_MS = RATE_LIMIT_WINDOW * 1000
PENALTY_TTL = 24 * 60 * 60

_SLIDING_WINDOW_LUA = """
local block_ttl = redis.call("TTL", KEYS[3])
if block_ttl > 0 then
    return {0, block_ttl}
end

redis.call("ZREMRANGEBYSCORE", KEYS[1], 0, ARGV[1] - ARGV[2])
local count = redis.call("ZCARD", KEYS[1])
if count >= tonumber(ARGV[3]) then
    local violations = redis.call("INCR", KEYS[2])
    redis.call("EXPIRE", KEYS[2], ARGV[5])
    local retry_after = 1
    if violations >= 10 then
        retry_after = 86400
    elseif violations >= 5 then
        retry_after = 300
    end
    redis.call("SET", KEYS[3], "1", "EX", retry_after)
    return {0, retry_after}
end

redis.call("ZADD", KEYS[1], ARGV[1], ARGV[4])
redis.call("PEXPIRE", KEYS[1], ARGV[2])
return {1, 0}
"""

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
    """基于 Redis ZSet 滑动窗口和 penalty box 的限流中间件

    对每个请求按客户端 IP 和请求路径建立 quota key。Lua 脚本在 Redis 内
    原子执行窗口裁剪、窗口计数、请求写入和惩罚递增，避免 fixed-window
    boundary burst 和多命令竞态。

    Args:
        request: FastAPI 请求对象
        call_next: 下一个中间件或路由处理函数

    Returns:
        请求的响应对象
    """
    client_ip = _get_client_ip(request)
    limit = _get_path_limit(request.url.path)
    key = f"rate_limit:{client_ip}:{request.url.path}"
    penalty_key = f"rate_limit:penalty:{client_ip}:{request.url.path}"
    block_key = f"rate_limit:block:{client_ip}:{request.url.path}"
    """
    TODO 不应该对IP限流,而是user_id限流
    Lua 滑动窗口已解决旧版 INCR 的竞态条件和固定窗口边界毛刺问题,
    但 IP 维度意味着同一 NAT 后多用户共享配额,可以改为:
    - 已登录用户: key = f"rate_limit:user:{user_id}:{path}"
    - 未登录用户: 保持 IP 维度
    (**更重的方案**:Nginx limit_req_zone 在反向代理层把请求截断,根本到不了应用层)
    """
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}:{time.monotonic_ns()}"
    try:
        allowed, retry_after = await redis_client.eval(
            _SLIDING_WINDOW_LUA,
            3,
            key,
            penalty_key,
            block_key,
            now_ms,
            RATE_LIMIT_WINDOW_MS,
            limit,
            member,
            PENALTY_TTL,
        )
    except Exception:
        logger.exception("限流 Redis 调用失败，fail-open 放行请求")
        return await call_next(request)

    if not int(allowed):
        return JSONResponse(
            status_code=429,
            content={"detail": "访问频率过高"},
            headers={"Retry-After": str(int(retry_after))},
        )

    return await call_next(request)
