from fastapi import Request, HTTPException
from app.core.redis import redis_client
from collections import defaultdict
import time
import logging
logger = logging.getLogger(__name__)
# 限制访问频率为 60次/min
RATE_LIMIT = 60
RATE_LIMIT_WINDOW = 60

# 使用 defalutdict 访问一个新 IP 时自动创建空列表，不用判断 key 是否存在
_local_counters: dict[str, list[float]] = defaultdict(list)

def _get_client_ip(request: Request) -> str:
    """
    ## 获取客户端IP
    请求路径：用户 -> Nginx(反向代理) -> FastAPI  

    """
    forwarded = request.headers.get("X-Forwarded-For")
    """
    用户真实 IP：203.0.113.50
    Nginx 收到后，在请求头里加上：
    X-Forwarded-For: 203.0.113.50, 10.0.0.1（代理 IP）
    X-Real-IP: 203.0.113.50
    """

    if forwarded:
        return forwarded.split(",")[0].strip()
    """例如: 
    "203.0.113.50, 10.0.0.1, 10.0.0.2"
    # split(",") → ["203.0.113.50", " 10.0.0.1", " 10.0.0.2"]
    # [0]        → "203.0.113.50"
    # .strip()   → "203.0.113.50"  （去前后空格）
    """
    
    real_ip = request.headers.get("X-Real-IP")

    if real_ip:
        return real_ip.strip()
    
    return request.client.host if request.client else "unknown"

def _loacl_rate_limit(client_ip: str) -> bool:
    """
    ## 本地内存限流
    若返回 True 则表示被限流
    """
    now = time.time()
    timestamps = _local_counters[client_ip] # 获取对应IP的访问时间戳列表
    
    # 删除过期的访问时间戳, 清除60s 之前的访问时间戳
    """
    timestamps 与 _local_counters[client_ip] 相同. 两个变量名, 但指向同一块内存 
    然后 下面 timestamps[:] = ...   
    直接对内存进行修改, 此时 _local_counters[client_ip] 也都改变  
    
    如果是 timestamps = ... 则会创建新的变量 这里是创建新列表
    此时 两个变量指向不同对象 _local_counters[client_ip] 没有改变
    """ 
    timestamps[:] = [t 
                     for t in timestamps 
                     if now - t < RATE_LIMIT_WINDOW]
    
    if len(timestamps) >= RATE_LIMIT:
        return True
    
    # 添加当前访问时间戳
    timestamps.append(now)
    return False

async def rate_limit_middleware(request: Request, call_next):
    """
    ## 限制访问频率
    利用递增incr 原子操作 一步搞定计数器
    若不限流则继续处理请求
    """
    client_ip = _get_client_ip(request)
    key = f"rate_limit:{client_ip}"

    try:
        count = await redis_client.incr(key)

        # ttl: 剩余过期时间
        ttl = await redis_client.ttl(key)
        if ttl < 0:
            # key没有过期时间, 需要补设
            await redis_client.expire(key, RATE_LIMIT_WINDOW)
        if count > RATE_LIMIT:
            raise HTTPException(status_code=429, detail="访问频率过高")
    except HTTPException:
        raise

    except Exception as e: # 捕获非HTTPException 异常
        # 此时认为redis异常, 使用本地内存限流
        logger.warning(f"redis异常, 使用本地内存限流: {e}")
        if _loacl_rate_limit(client_ip):
            raise HTTPException(status_code=429, detail="访问频率过高")

    return await call_next(request)