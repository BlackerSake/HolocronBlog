# 点赞热 Key 并发压测报告
    2026-09-10 CST 上午10:37:13
- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮,取中位数
- 模型：单用户、单文章热 Key,关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 184.58 | 52.36 | 101.66 | 142.41 | 100.00% | `{200: 3000}` |
| 25 | 73.03 | 329.86 | 829.33 | 1295.64 | 100.00% | `{200: 3000}` |
| 50 | 77.61 | 621.34 | 1803.05 | 2964.49 | 100.00% | `{200: 3000}` |
| 100 | 75.94 | 1257.44 | 3842.20 | 5947.26 | 100.00% | `{200: 3000}` |
| 200 | 59.44 | 3044.58 | 9351.27 | 13440.75 | 99.97% | `{200: 2999, 'ReadError': 1}` |

- 压测后点赞状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 1, 'is_liked': False}`

压测失败：存在非 200 响应

## 解析
并发 10 -> 25,RPS 从 184 跌到 73,之后稳定在 ~75,延迟随并发线性增长（100 并发时 100/76 ≈ 1.3s,符合Little's Law）.这不是"没到瓶颈",而是已经撞墙且墙是争抢型的：吞吐量随并发上升反而下降,是典型的单写者锁争用特征.  
**墙在哪？**注意压测脚本：bool(index % 2) —— 每个请求都在切换点赞状态,每个请求都 
changed=True,于是每个请求都走到 routers/likes.py:62 的 create_notification(db, ...)：同步 INSERT + commit 到 SQLite.再加上 Stream consumer 同时在后台批量写 likes 表抢同一把写锁.*看起来以为在压 Redis点赞链路,实际在压 SQLite 的 fsync 和文件锁*.SQLite 非 WAL 模式下写事务全局串行,写者多了互相busy-wait,读者还被阻塞——并发越高越慢,完全对上曲线.

## 更改
1. 把脚本里的 bool(index % 2) 改成 True（恒点赞,第二次起 changed=False,不走通知写库）,重跑并发50.如果 RPS 跳到几百上千,锁死结论：瓶颈就是通知的同步写.这两个数字（幂等路径 vs
切换路径）都值得测.
1. sqlite3 holocron.db "PRAGMA journal_mode;" — 大概率是 delete,不是 wal.

  检查两处压测客户端：确认服务确实是 --workers 4 起的；
  httpx.AsyncClient 默认max_keepalive_connections=20,高并发档会客户端侧排队污染延迟,建 client 时加 limits=httpx.Limits(max_connections=300, max_keepalive_connections=300).

# 点赞热 Key 并发压测报告
### **把脚本里的 bool(index % 2) 改成 True（恒点赞）**
```
- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮,取中位数
- 模型：单用户、单文章热 Key,关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 214.86 | 44.90 | 91.60 | 131.67 | 100.00% | `{200: 3000}` |
| 25 | 136.36 | 177.35 | 458.38 | 686.72 | 100.00% | `{200: 3000}` |
| 50 | 123.62 | 389.22 | 1092.54 | 1724.09 | 100.00% | `{200: 3000}` |
| 100 | 113.74 | 820.44 | 2413.23 | 3766.89 | 100.00% | `{200: 3000}` |
| 200 | 97.57 | 1868.40 | 5558.14 | 8018.90 | 100.00% | `{200: 3000}` |

- 压测后点赞状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 2, 'is_liked': True}`
```
### **把脚本里的 bool(index % 2) 改成 False**
```
- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮,取中位数
- 模型：单用户、单文章热 Key,关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 211.59 | 45.65 | 93.05 | 129.54 | 100.00% | `{200: 3000}` |
| 25 | 122.32 | 197.50 | 517.05 | 756.66 | 100.00% | `{200: 3000}` |
| 50 | 96.33 | 499.96 | 1490.48 | 2284.66 | 100.00% | `{200: 3000}` |
| 100 | 96.98 | 971.74 | 2792.34 | 4107.61 | 100.00% | `{200: 3000}` |
| 200 | 78.65 | 2326.77 | 7296.22 | 10143.84 | 100.00% | `{200: 3000}` |

- 压测后点赞状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 1, 'is_liked': False}`
```


# 缓存并发压测报告
### **python scripts/benchwork_cache_governance.py --path / --concurrencies 50  # 纯框架**

```
- 目标: `http://127.0.0.1:8858/`
- 每轮请求数: `1000`
- 每档轮数: `3`
- 每档并发预热轮数: `1`

| 并发数 | 中位吞吐量 RPS | 平均延迟 ms | p95 ms | p99 ms | 客户端 CPU | 成功率 | 状态码 | 传输错误 |
|---:|---:|---:|---:|---:|---:|---:|:---|:---|
| 50 | 323.49 | 136.93 | 383.80 | 584.84 | 86.38% | 100.00% | `{200: 3000}` | `{}` |

- 峰值并发数: `50`
- 峰值吞吐量_rps: `323.49`
- 峰值p95延迟_ms: `383.80
```
### **python scripts/benchwork_cache_governance.py --path /health/db --concurrencies 50  # +1次 SQLite**
```
- 目标: `http://127.0.0.1:8858/health/db`
- 每轮请求数: `1000`
- 每档轮数: `3`
- 每档并发预热轮数: `1`

| 并发数 | 中位吞吐量 RPS | 平均延迟 ms | p95 ms | p99 ms | 客户端 CPU | 成功率 | 状态码 | 传输错误 |
|---:|---:|---:|---:|---:|---:|---:|:---|:---|
| 50 | 308.10 | 144.55 | 454.95 | 637.53 | 83.68% | 100.00% | `{200: 3000}` | `{}` |

- 峰值并发数: `50`
- 峰值吞吐量_rps: `308.10`
- 峰值p95延迟_ms: `454.95`
```
### **python scripts/benchwork_cache_governance.py --path /articles/1111/like-status --concurrencies 50  #需带 token,最接近点赞路径(仿benchwork_likes.py添加登录)**
```
- 目标: `http://127.0.0.1:8858/articles/1111/like-status`
- 每轮请求数: `1000`
- 每档轮数: `3`
- 每档并发预热轮数: `1`

| 并发数 | 中位吞吐量 RPS | 平均延迟 ms | p95 ms | p99 ms | 客户端 CPU | 成功率 | 状态码 | 传输错误 |
|---:|---:|---:|---:|---:|---:|---:|:---|:---|
| 5 | 245.69 | 19.02 | 29.42 | 47.97 | 56.66% | 100.00% | `{200: 3000}` | `{}` |

- 峰值并发数: `5`
- 峰值吞吐量_rps: `245.69`
- 峰值p95延迟_ms: `29.42`
```
## 结论
由 GET / 数据可知,即使是纯框架路径,c=50.cpu跑到86%, rps也只有323.绝大部分是压测客户端自己忙不过来——asyncio 单线程的 httpx 客户端在 50 并发下 CPU饱和,请求在客户端排队,**把客户端的排队时间测成了服务端延迟**
这也解释了之前所有的怪象：
  - 点赞路径 45ms 的"地板" —— 是客户端开销
  - RPS 随并发上升反而下降 —— 并发越高,客户端事件循环越忙,每个连接的服务越慢
  - like-status 在 c=5（CPU 57%,没饱和）时平均延迟 19ms —— 这才是真实服务端延迟的量级,而且 19ms里可能还带着客户端开销
# 更换测压工具: wrk
### 测试:
```
(HolocronBlog) j0hnny@the-only-skywalker:/Alpha/College_new/HolocronBlog$ ./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   138.73ms  258.19ms   1.87s    90.80%
    Req/Sec    41.09     36.80   310.00     68.35%
  Latency Distribution
     50%   45.43ms
     75%  118.05ms
     90%  352.75ms
     99%    1.39s 
  1810 requests in 35.10s, 372.02KB read
  Socket errors: connect 0, read 153, write 0, timeout 256
  Non-2xx or 3xx responses: 153
Requests/sec:     51.57
Transfer/sec:     10.60KB
status_code 分析
```

## **SQLite 非 WAL 模式下,写事务锁住整个数据库文件,连 SELECT 都被阻塞** 
绝大多数请求很快,一小撮请求卡到天荒地老: *典型的锁竞争*  
51 RPS + 256 个超时 + 153 个 500,这就是 SQLite 的真实天花板  
## 修法：
**WAL + busy_timeout,一个共享 engine 工厂: @app/core/database.py 16~32**

### 纯框架:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/**
```
Running 35s test @ http://127.0.0.1:8858/
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     7.81ms    5.57ms 122.06ms   91.78%
    Req/Sec     1.63k   469.64     2.83k    67.64%
  Latency Distribution
     50%    6.80ms
     75%    9.25ms
     90%   12.20ms
     99%   26.88ms
  227946 requests in 35.10s, 33.48MB read
Requests/sec:   6494.09
Transfer/sec:      0.95MB
```
### 一次sql查询:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/health/db**
```
Running 35s test @ http://127.0.0.1:8858/health/db
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    29.18ms   16.25ms 164.11ms   71.85%
    Req/Sec   426.65    129.61   700.00     63.43%
  Latency Distribution
     50%   26.75ms
     75%   36.47ms
     90%   47.34ms
     99%   88.27ms
  59566 requests in 35.07s, 8.58MB read
Requests/sec:   1698.33
Transfer/sec:    250.44KB
```
### 点赞接口:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   216.52ms  308.17ms   1.99s    87.93%
    Req/Sec    75.71     33.74   227.00     67.07%
  Latency Distribution
     50%   97.06ms
     75%  201.14ms
     90%  623.99ms
     99%    1.47s 
  10726 requests in 35.10s, 2.16MB read
  Socket errors: connect 0, read 0, write 0, timeout 90
Requests/sec:    305.60
Transfer/sec:     62.97KB
```
## 结论
**这才是真正的数据!**  
**纯框架：6529 RPS**: *这是上限.FastAPI + Uvicorn,本地回环,-c50,什么业务逻辑都没有,就是路由 + 序列化 + 返回*

**一次 SQL 查询**：1288 RPS
RPS 从 6529 -> 1288,掉了 5 倍；p50 从 6.67ms -> 34.74ms,慢了 5 倍.
这两个 5 倍是同一件事：每次请求多了一次 SQL 查询,整个链路被拉长了 5 倍

## 链路优化

### 一次sql查询:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/health/db**
```
Running 35s test @ http://127.0.0.1:8858/health/db
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    31.78ms   16.42ms 194.01ms   77.85%
    Req/Sec   390.08    132.58   777.00     73.77%
  Latency Distribution
     50%   28.71ms
     75%   38.60ms
     90%   49.84ms
     99%   93.80ms
  54436 requests in 35.07s, 7.84MB read
Requests/sec:   1551.99
Transfer/sec:    228.86KB
```
### 点赞接口:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   206.70ms  345.62ms   1.98s    85.99%
    Req/Sec   156.73     85.94   575.00     68.44%
  Latency Distribution
     50%   26.74ms
     75%  247.50ms
     90%  710.98ms
     99%    1.51s 
  22045 requests in 35.09s, 4.44MB read
  Socket errors: connect 0, read 0, write 0, timeout 95
Requests/sec:    628.19
Transfer/sec:    129.42KB
```
## 结论
一次sql查询有略微的rps损失,而点赞接口伴随着代码优化获得的2倍的rps提升

## 再次测试
`pytest -x -q` 269passed,3 warnings 不重要.算全绿  
**更改系统为 performance**  
`echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` 

### 点赞接口:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    28.88ms   85.36ms 785.57ms   94.99%
    Req/Sec   135.80    179.95   656.00     86.36%
  Latency Distribution
     50%    7.61ms
     75%   16.65ms
     90%   37.13ms
     99%  556.69ms
  664 requests in 35.10s, 136.56KB read
  Socket errors: connect 0, read 40, write 0, timeout 45
  Non-2xx or 3xx responses: 40
Requests/sec:     18.92
Transfer/sec:      3.89KB
```
*存在大量报错: sqlite3.OperationalError: database is locked*  

## 检查原因: 还有人在吃锁😡
两处裸 engine：cache_consistency.py:154 和 cache_rebuild.py:39 *没改到*
*清空脏数据*:
之前压 article 1111 已经超过 30 分钟——点赞缓存的 30 分钟 TTL 在压测中途到期了
*于是:*缓存重建 -> 从 DB重新预热 -> 但 DB 和 Redis 已经漂移（db_counter=-7）-> 重建出的集合里没有 benchuser -> 下一个请求 SADD changed=1 -> 通知 INSERT + XADD -> 写锁排队

### 点赞接口:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   205.72ms  349.33ms   2.00s    86.18%
    Req/Sec   132.60     82.11   490.00     68.12%
  Latency Distribution
     50%   26.62ms
     75%  238.44ms
     90%  713.87ms
     99%    1.55s 
  18602 requests in 35.09s, 3.74MB read
  Socket errors: connect 0, read 0, write 0, timeout 125
Requests/sec:    530.10
Transfer/sec:    109.21KB
```
### MODE=toggle:**MODE=toggle ./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   207.11ms  349.11ms   2.00s    86.11%
    Req/Sec   101.22     68.28   480.00     73.94%
  Latency Distribution
     50%   28.70ms
     75%  237.17ms
     90%  721.64ms
     99%    1.54s 
  14194 requests in 35.10s, 2.86MB read
  Socket errors: connect 0, read 0, write 0, timeout 160
Requests/sec:    404.38
Transfer/sec:     83.30KB
```
### 纯框架:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/**
```
Running 35s test @ http://127.0.0.1:8858/
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     8.98ms    6.68ms 127.36ms   90.04%
    Req/Sec     1.45k   538.27     3.53k    64.92%
  Latency Distribution
     50%    7.38ms
     75%   10.88ms
     90%   14.84ms
     99%   36.96ms
  201967 requests in 35.10s, 29.66MB read
Requests/sec:   5754.74
Transfer/sec:    865.46KB
```
### 一次sql查询:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/health/db**
```
Running 35s test @ http://127.0.0.1:8858/health/db
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    47.55ms   24.78ms 292.92ms   75.85%
    Req/Sec   260.18    110.43   830.00     76.02%
  Latency Distribution
     50%   44.59ms
     75%   57.63ms
     90%   75.98ms
     99%  135.71ms
  36292 requests in 35.10s, 5.23MB read
Requests/sec:   1033.96
Transfer/sec:    152.47KB
```

## 修改:
##### ***关键:***
**升级 redis-py 8.0** 后默认 socket_timeout 从 None 变为5s,阻塞读语义被破坏,引发 consumer 静默死亡 -> 缓存预热失效 -> 请求路径降级到 DB -> 熔断打开 ->雪崩.  
**症状**是 p99 恶化,根因在客户端默认值变更,定位手段是 py-spy + 连接参数审计.  
1.*--no-access-log 加进 bench.sh——对*
2.*socket_timeout=None,   # redis-py 8.0 默认 5s,会杀死阻塞读(XREADGROUP/pubsub)*

### 点赞接口:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   187.93ms  329.87ms   1.99s    86.44%
    Req/Sec   205.64    104.68     0.98k    70.18%
  Latency Distribution
     50%   15.56ms
     75%  211.79ms
     90%  661.70ms
     99%    1.47s 
  28980 requests in 35.05s, 5.83MB read
  Socket errors: connect 0, read 0, write 0, timeout 106
Requests/sec:    826.85
Transfer/sec:    170.33KB
```
### MODE=toggle:**MODE=toggle ./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   205.30ms  351.63ms   1.97s    86.10%
    Req/Sec   215.01    119.94     1.14k    71.93%
  Latency Distribution
     50%   18.02ms
     75%  247.62ms
     90%  722.32ms
     99%    1.54s 
  30195 requests in 35.06s, 6.07MB read
  Socket errors: connect 0, read 0, write 0, timeout 77
Requests/sec:    861.23
Transfer/sec:    177.41KB
```
## 再测试拐点:之前熔断导致的全链路db兜底已经解决
### 100并发:**./scripts/bench_wrk.sh -t4 -c100 -d35s --latency   -s scripts/bench_like.lua   http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   209.92ms  367.56ms   2.00s    85.93%
    Req/Sec   187.82    118.10   810.00     71.49%
  Latency Distribution
     50%   14.31ms
     75%  249.24ms
     90%  761.50ms
     99%    1.58s 
  26428 requests in 35.06s, 5.32MB read
  Socket errors: connect 0, read 0, write 0, timeout 414
Requests/sec:    753.88
Transfer/sec:    155.30KB
```
### 200并发:**./scripts/bench_wrk.sh -t4 -c200 -d35s --latency   -s scripts/bench_like.lua   http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 200 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   288.87ms  411.36ms   1.99s    83.78%
    Req/Sec   194.72    110.34     1.02k    73.21%
  Latency Distribution
     50%   15.17ms
     75%  494.87ms
     90%  908.16ms
     99%    1.65s 
  27411 requests in 35.09s, 5.51MB read
  Socket errors: connect 0, read 0, write 0, timeout 700
Requests/sec:    781.23
Transfer/sec:    160.93KB
```
## 解析:
并发翻 4 倍,吞吐不动,超时数随队列变长（106 -> 414 -> 700）——**CPU 到顶**容量 ≈ 800 RPS（本机、wrk同机抢核的下限值）.p50 始终 15ms 说明快路径依然快,涨的全是排队  
**Python/SQLite 层的油水到此榨干**


# 迁移到PGSQL后
### 纯框架:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/**
```
Running 35s test @ http://127.0.0.1:8858/
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     3.48ms    1.81ms  26.08ms   76.96%
    Req/Sec     3.54k     1.07k    5.67k    59.29%
  Latency Distribution
     50%    3.01ms
     75%    4.28ms
     90%    5.87ms
     99%    9.56ms
  493449 requests in 35.02s, 72.47MB read
Requests/sec:  14088.63
Transfer/sec:      2.07MB
```
### 一次sql查询:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/health/db**
```
Running 35s test @ http://127.0.0.1:8858/health/db
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    16.86ms    8.87ms 138.74ms   94.26%
    Req/Sec   747.93    135.05     1.10k    68.71%
  Latency Distribution
     50%   15.03ms
     75%   18.43ms
     90%   22.50ms
     99%   65.91ms
  104285 requests in 35.03s, 15.02MB read
Requests/sec:   2976.68
Transfer/sec:    438.94KB
```
### 点赞链路:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    46.84ms   30.02ms 623.04ms   82.62%
    Req/Sec   269.71     83.73     1.15k    68.85%
  Latency Distribution
     50%   38.48ms
     75%   58.51ms
     90%   84.79ms
     99%  141.45ms
  38145 requests in 35.09s, 7.67MB read
Requests/sec:   1087.04
Transfer/sec:    223.95KB
```
### MODE=toggle:**MODE=toggle ./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 50 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    43.99ms   26.77ms 342.96ms   83.21%
    Req/Sec   286.08     91.15     1.14k    66.38%
  Latency Distribution
     50%   36.37ms
     75%   54.49ms
     90%   79.51ms
     99%  129.48ms
  40465 requests in 35.07s, 8.14MB read
Requests/sec:   1153.84
Transfer/sec:    237.71KB
```
## 再测试拐点
### 100并发:**./scripts/bench_wrk.sh -t4 -c100 -d35s --latency   -s scripts/bench_like.lua   http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   101.12ms   57.98ms 840.70ms   77.28%
    Req/Sec   256.83     74.70     1.07k    75.04%
  Latency Distribution
     50%   83.60ms
     75%  128.10ms
     90%  179.96ms
     99%  282.46ms
  36409 requests in 35.08s, 7.33MB read
Requests/sec:   1037.83
Transfer/sec:    213.81KB
```
## 200并发:**./scripts/bench_wrk.sh -t4 -c200 -d35s --latency   -s scripts/bench_like.lua   http://127.0.0.1:8858/articles/1111/like**
```
Running 35s test @ http://127.0.0.1:8858/articles/1111/like
  4 threads and 200 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   211.20ms  133.81ms   1.49s    82.92%
    Req/Sec   249.15     85.08     1.18k    79.23%
  Latency Distribution
     50%  167.41ms
     75%  268.61ms
     90%  373.86ms
     99%  691.40ms
  35405 requests in 35.06s, 7.12MB read
Requests/sec:   1009.97
Transfer/sec:    208.07KB
```
# 解析:

在数据库更换为`PostgreSQL`后,数据方面获得明显提升:


| 测试 | SQLite RPS | SQLite p99 | PG RPS | PG p99 | 变化 |
|---:|---:|---:|---:|---:|---|
| 纯框架 | 5754.74 | 36.96 ms | 14088.63 | 9.56 ms | RPS ×2.45 · p99 −74% |
| 一次SQL | 1033.96 | 135.71 ms | 2976.68 | 65.91 ms | RPS ×2.88 · p99 −51% |
| 点赞链路 | 826.85 | 1470 ms | 1087.04 | 141.45 ms | RPS ×1.31 · p99 −90% |
| toggle | 861.23 | 1540 ms | 1153.84 | 129.48 ms | RPS ×1.34 · p99 −92% |
| 100并发 | 753.88 | 1580 ms | 1037.83 | 282.46 ms | RPS ×1.38 · p99 −82% |
| 200并发 | 781.23 | 1650 ms | 1009.97 | 691.40 ms | RPS ×1.29 · p99 −58% |


**P99 延迟下降约 90%**  
*此前:* 锁竞争 -> redis 超时 -> DB兜底 -> 排队雪崩. 如今这个sqlite的结构性质病根已经拔除  
**sqlite 的结构病根:***SQLite 在同一数据库文件上同一时刻只能有一个写事务*；WAL 模式可以显著改善读写并发,但不能让多个写事务真正并行执行.  
PostgreSQL 则可以让多个事务并发执行,通过行级锁、MVCC 等机制减少不必要的全局阻塞.    
点赞场景恰好是写入密集 + 短事务——单个事务很快,但并发度高.SQLite 的锁粒度让这些快事务被迫串成一条线,吞吐上限被死死钉在"单事务耗时 × 串行度"上  

