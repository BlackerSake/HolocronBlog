import time

from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.redis import redis_client
import logging
logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_WINDOW_MS = RATE_LIMIT_WINDOW * 1000
PENALTY_TTL = 24 * 60 * 60
_DEFAULT_BUCKET = (20, 1.0)       # burst=20, refill=1 token/s
_PATH_BUCKETS: list[tuple[str, tuple[int, float]]] = [
    ("/api/v1/register", (3, 3 / 60)),
    # 接口: brust = 3 refill = 3 token/min
    ("/api/v1/login", (5, 5 / 60)),
    # 登录: brust = 5 refill = 5 token/,on
]
# 令牌桶lua脚本
_TOKEN_BUCKET_LUA = """
local tokens = tonumber(redis.call("GET", KEYS[1]))
local updated_at = tonumber(redis.call("GET", KEYS[2]))
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

-- 首次访问:桶不存在 -> 创建满令牌桶
if tokens == nil then
    tokens = capacity
    updated_at = now
end

-- 记录距离上次访问的时间 (0,...) 防止负数错误
local elapsed = math.max(0, now - updated_at) / 1000
-- 当前令牌 = 剩余令牌 + 距离上次访问的时间 * 填充速率
tokens = math.min(capacity, tokens + elapsed * refill_rate)

-- 令牌不够 -> 计算等待时间 -> 更新令牌桶 -> 更新时间戳
if tokens < cost then
    local retry_after = math.ceil((cost - tokens) / refill_rate)
    redis.call("SET", KEYS[1], tokens, "PX", ttl)
    redis.call("SET", KEYS[2], now, "PX", ttl)
    return {0, retry_after}
    -- 响应格式: [是否允许访问, 剩余时间(秒)]
end

-- 令牌足够 -> 减去消耗的令牌 -> 更新令牌桶 -> 更新时间戳 -> 放行
tokens = tokens - cost
redis.call("SET", KEYS[1], tokens, "PX", ttl)
redis.call("SET", KEYS[2], now, "PX", ttl)
return {1, 0}
"""
# 滑动窗口Lua脚本
_SLIDING_WINDOW_LUA = """
-- 检查封禁标记
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


def _get_token_bucket(path: str) -> tuple[int, float]:
    """根据请求路径获取 token bucket 的容量和填充速率。"""
    for prefix, bucket in _PATH_BUCKETS:
        if path.startswith(prefix):
            return bucket
    return _DEFAULT_BUCKET


async def rate_limit_middleware(request: Request, call_next):
    """基于 Redis token bucket、ZSet 滑动窗口和 penalty box 的限流中间件

    对每个请求按客户端 IP 和请求路径建立 quota key。Lua 脚本在 Redis 内
    原子执行 token 消耗、窗口裁剪、窗口计数、请求写入和惩罚递增。token
    bucket 允许短 burst，sliding window 约束持续吞吐，penalty box 处理连续
    超限。

    Args:
        request: FastAPI 请求对象
        call_next: 下一个中间件或路由处理函数

    Returns:
        请求的响应对象
    """
    client_ip = _get_client_ip(request)
    limit = _get_path_limit(request.url.path)
    capacity, refill_rate = _get_token_bucket(request.url.path)

    key = f"rate_limit:{client_ip}:{request.url.path}"
    # 令牌桶剩余令牌数的 key
    bucket_key = f"rate_limit:bucket:{client_ip}:{request.url.path}"
    # 令牌桶上次更新时间的 key
    bucket_ts_key = f"rate_limit:bucket_ts:{client_ip}:{request.url.path}"

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
        bucket_allowed, bucket_retry_after = await redis_client.eval(
            _TOKEN_BUCKET_LUA,
            2,
            bucket_key, # KEYS[1]
            bucket_ts_key, # KEYS[2]
            now_ms, # ARGV[1]
            capacity,
            refill_rate,
            1,
            RATE_LIMIT_WINDOW_MS, # ARGV[5]
        )

        # 令牌桶未允许 -> 响应429
        if not int(bucket_allowed):
            return JSONResponse(
                status_code=429,
                content={"detail": "访问频率过高"},
                headers={"Retry-After": str(int(bucket_retry_after))},
            )

        allowed, retry_after = await redis_client.eval(
            _SLIDING_WINDOW_LUA, # LUA 脚本
            3,  # 表示前三个参数是 key
            key,    # KEYS[1] = ZSet: 滑动窗口的时间戳集合
            penalty_key, # KEYS[2] = String: 窗口内计数
            block_key, # KEYS[3] = String: 封禁标记
            now_ms, # ARGV[1] = 当前时间戳
            RATE_LIMIT_WINDOW_MS, # ARGV[2] = 窗口大小
            limit, # ARGV[3] = 窗口内最大请求次数
            member, # ARGV[4] = ZSet 成员
            PENALTY_TTL, # ARGV[5] = 惩罚窗口 TTL
        )
    except Exception:
        logger.exception("限流 Redis 调用失败，fail-open 放行请求")
        return await call_next(request)
    # 窗口未允许 -> 响应429
    if not int(allowed):
        return JSONResponse(
            status_code=429,
            content={"detail": "访问频率过高"},
            headers={"Retry-After": str(int(retry_after))},
        )
    # 令牌桶和滑动窗口都允许 -> 放行,交给下一个中间件或路由处理函数处理
    return await call_next(request)