# 点赞主链路
```
用户点击点赞
->Vue切换目标状态
->Axios 携带JWT发PUT请求
->FastAPI 鉴权并确认文章/评论存在
->Redis 预热点赞集合
-> Lua原子执行 SADD/SREM + SCARD + XADD
-> API 立即返回点赞状态和数量
-> Redis Stream 消费者批量写入数据库
-> 创建通知 + WebSocket 通知当前user
```

## 后端路由入口

>对于文章点赞:
- 路由:[app/routers/likes.py:24](../app/routers/likes.py#L24)
- 鉴权:[app/core/dependencies.py:55](../app/core/dependencies.py#L55)
- 请求,响应结构:[app/schemas/like.py:28](../app/schemas/like.py#L28)


执行顺序:
---
### 1. 从JWT令牌中解析并获取当前认证用户
[get_current_user](../app/core/dependencies.py#L55)  
1. `...= jwt.decode(...)` (-> dict[str, Any])
2. 优先读取 Redis 用户缓存,命中则免去每次 请求的users表查询
3. redis 没有缓存则 查询db
如何查询的缓存呢?  
```python
cache_key = _user_cache_key(username)
user: User | None = None
try:
    cached = await redis_client.get(cache_key)
```

### 2.根据slug找文章
[get_article_like_target()](../app/services/like_service.py#L348)
1. 若有cached,查询redis_client
2. 若无cached,查询db,并设置缓存
slug这里的redis查询是这样的:
```python
key = f"{LIKE_TARGET_CACHE_PREFIX}{slug}"
try:
    cached = await redis_client.get(key)
```

### 3.设置Redis中点赞目标状态并返回计数(重点)

[change_like_status_cached()](../app/services/like_service.py#L439)  
1. 生成点赞功能使用的 Redis 键名元组
2. 确保没有触发熔断,若熔断触发,则直接动db
3. 熔断未触发:等待缓存预热,`redis_client.eval`执行Lua脚本
4. 记录 redis点赞实时链路的成功与失败,并根据情况触发熔断

#### Lua 原子执行 `SADD/SREM + SCARD + XADD`

Lua脚本位置:[app/services/like_service.py:18](../app/services/like_service.py#L18)

`redis_client.eval`一次执行以下操作:

```text
修改 Redis 点赞集合
->重新计算点赞数
->状态真正变化时写入 Redis Stream
->返回最终状态和点赞数
```

调用Lua脚本时,前两个参数是 Redis Key:

```python
KEYS[1] = users_key       # 例如 like:article:10:users
KEYS[2] = LIKE_STREAM     # like:events
```

剩余参数放在 `ARGV` 中:

```python
ARGV[1] = user_id
ARGV[2] = target_id
ARGV[3] = target_type
ARGV[4] = LIKE_STREAM_MAXLEN
ARGV[5] = is_liked
```

1. 根据期望状态修改点赞用户集合:
   - `is_liked == 1`: 使用 `SADD` 添加用户
   - `is_liked == 0`: 使用 `SREM` 移除用户
2. `SADD` 或 `SREM` 的返回值保存到 `changed`:
   - 返回 `1`: 本次真的发生了变化
   - 返回 `0`: 原状态已经符合要求,没有变化
3. 使用 `SCARD` 获取点赞用户集合的成员数量,作为实时点赞数
4. 只有 `changed == 1` 时才使用 `XADD` 写入 `like:events`
5. 最后返回 `{desired, count, changed}`

对应代码:

```lua
local desired = tonumber(ARGV[5])
local changed

if desired == 1 then
    changed = redis.call("SADD", KEYS[1], ARGV[1])
else
    changed = redis.call("SREM", KEYS[1], ARGV[1])
end

local count = redis.call("SCARD", KEYS[1])
if changed == 1 then
    redis.call(
        "XADD", KEYS[2], "MAXLEN", "~", ARGV[4], "*",
        "user_id", ARGV[1],
        "target_id", ARGV[2],
        "target_type", ARGV[3],
        "is_liked", desired
    )
end

return {desired, count, changed}
```

例如第一次点赞:

```text
SADD 返回 1
SCARD 返回 3
XADD 写入一条 is_liked=1 的事件
最终返回 [1, 3, 1]
```

重复点赞时:

```text
SADD 返回 0
SCARD 返回 3
不会重复写入 Stream
最终返回 [1, 3, 0]
```

这里的“原子”指Lua脚本在Redis中作为一个整体执行,其他Redis命令不会插入到这几个操作之间,因此不会出现状态已修改但计数或事件还没同步的中间状态。

### 4. 为新增的点赞创建通知

[append_notification_event()](../app/core/notification_stream.py)  
1. 只有 `status["is_liked"]` 和 `status["changed"]` 同时为 `True` 时才创建通知
2. `status["is_liked"]` 用于判断这次是“点赞”还是“取消点赞”
3. `status["changed"]` 用于避免重复提交相同状态时重复创建通知
4. 文章点赞通知类型是 `like_article`，接收者是文章作者
5. 评论点赞通知类型是 `like_comment`，接收者是评论作者
6. 通知事件通过 Redis Stream 异步写入通知表

文章点赞对应代码:
```python
if status["is_liked"] and status["changed"]:
    await append_notification_event(
        initiator_id=current_user.id,
        recipient_id=author_id,
        type="like_article",
        content="有人赞了你的文章",
        article_id=article_id,
    )
```

重点看:
- [文章点赞通知](../app/routers/likes.py#L62)
- [评论点赞通知](../app/routers/likes.py#L116)
- [通知 Stream 写入](../app/core/notification_stream.py)

### 5. 点赞状态发生变化,发送`like_changed` WebSocket消息

1. 只有 `status["changed"]` 为 `True` 时才发送消息
2. 点赞和取消点赞都会发送，因为两者都会改变状态
3. 使用 `wbmanager.send_personal_message()` 给当前用户发送个人消息
4. 消息内容包含 `user_id`、`target_id`、`target_type`、`like_count`、`is_liked` 和 `changed`
5. 前端收到 `like_changed` 后，再转成浏览器事件供其他页面刷新

对应代码:
```python
if status["changed"]:
    await wbmanager.send_personal_message(current_user.id, json.dumps({
        "type": "like_changed",
        "user_id": current_user.id,
        **status,
    }))
```

重点看:
- [文章点赞 WebSocket](../app/routers/likes.py#L70)
- [评论点赞 WebSocket](../app/routers/likes.py#L125)
- [WebSocket 管理器](../app/core/websocket.py)


>评论点赞是同一套结构：


