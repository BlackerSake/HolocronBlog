# 点赞热 Key 并发压测报告
    2026-09-10 CST 上午10:37:13
- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮，取中位数
- 模型：单用户、单文章热 Key，关闭接口限流

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
并发 10 → 25，RPS 从 184 跌到 73，之后稳定在 ~75，延迟随并发线性增长（100 并发时 100/76 ≈ 1.3s，符合Little's Law）。这不是"没到瓶颈"，而是已经撞墙且墙是争抢型的：吞吐量随并发上升反而下降，是典型的单写者锁争用特征。
**墙在哪？**看你的压测脚本：bool(index % 2) —— 每个请求都在切换点赞状态，每个请求都 
changed=True，于是每个请求都走到 routers/likes.py:62 的 create_notification(db, ...)：同步 INSERT + commit 到 SQLite。再加上 Stream consumer 同时在后台批量写 likes 表抢同一把写锁。*你以为在压 Redis点赞链路，实际在压 SQLite 的 fsync 和文件锁*。SQLite 非 WAL 模式下写事务全局串行，写者多了互相busy-wait，读者还被阻塞——并发越高越慢，完全对上曲线。

# 更改
1. 把脚本里的 bool(index % 2) 改成 True（恒点赞，第二次起 changed=False，不走通知写库），重跑并发50。如果 RPS 跳到几百上千，锁死结论：瓶颈就是通知的同步写。这两个数字（幂等路径 vs
切换路径）都值得测，简历上分开写。
2. sqlite3 holocron.db "PRAGMA journal_mode;" — 大概率是 delete，不是 wal。

  另外检查两处压测客户端：确认服务确实是 --workers 4 起的；httpx.AsyncClient 默认
  max_keepalive_connections=20，高并发档会客户端侧排队污染延迟，建 client 时加
  limits=httpx.Limits(max_connections=300, max_keepalive_connections=300)。

# 点赞热 Key 并发压测报告
## **把脚本里的 bool(index % 2) 改成 True（恒点赞）**
- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮，取中位数
- 模型：单用户、单文章热 Key，关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 214.86 | 44.90 | 91.60 | 131.67 | 100.00% | `{200: 3000}` |
| 25 | 136.36 | 177.35 | 458.38 | 686.72 | 100.00% | `{200: 3000}` |
| 50 | 123.62 | 389.22 | 1092.54 | 1724.09 | 100.00% | `{200: 3000}` |
| 100 | 113.74 | 820.44 | 2413.23 | 3766.89 | 100.00% | `{200: 3000}` |
| 200 | 97.57 | 1868.40 | 5558.14 | 8018.90 | 100.00% | `{200: 3000}` |

- 压测后点赞状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 2, 'is_liked': True}`

## **把脚本里的 bool(index % 2) 改成 False**
- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮，取中位数
- 模型：单用户、单文章热 Key，关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 211.59 | 45.65 | 93.05 | 129.54 | 100.00% | `{200: 3000}` |
| 25 | 122.32 | 197.50 | 517.05 | 756.66 | 100.00% | `{200: 3000}` |
| 50 | 96.33 | 499.96 | 1490.48 | 2284.66 | 100.00% | `{200: 3000}` |
| 100 | 96.98 | 971.74 | 2792.34 | 4107.61 | 100.00% | `{200: 3000}` |
| 200 | 78.65 | 2326.77 | 7296.22 | 10143.84 | 100.00% | `{200: 3000}` |

- 压测后点赞状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 1, 'is_liked': False}`



# 缓存并发压测报告
 ## **python scripts/benchwork_cache_governance.py --path / --concurrencies 50  # 纯框架**
- 目标: `http://127.0.0.1:8858/`
- 每轮请求数: `1000`
- 每档轮数: `3`
- 每档并发预热轮数: `1`

| 并发数 | 中位吞吐量 RPS | 平均延迟 ms | p95 ms | p99 ms | 客户端 CPU | 成功率 | 状态码 | 传输错误 |
|---:|---:|---:|---:|---:|---:|---:|:---|:---|
| 50 | 323.49 | 136.93 | 383.80 | 584.84 | 86.38% | 100.00% | `{200: 3000}` | `{}` |

- 峰值并发数: `50`
- 峰值吞吐量_rps: `323.49`
- 峰值p95延迟_ms: `383.80`
## **python scripts/benchwork_cache_governance.py --path /health/db --concurrencies 50  # +1次 SQLite**
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
## **python scripts/benchwork_cache_governance.py --path /articles/1111/like-status --concurrencies 50  #需带 token,最接近点赞路径(仿benchwork_likes.py添加登录)**
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

## 结论
由 GET / 数据可知,即使是纯框架路径,c=50.cpu跑到86%, rps也只有323.绝大部分是压测客户端自己忙不过来——asyncio 单线程的 httpx 客户端在 50 并发下 CPU饱和,请求在客户端排队,**把客户端的排队时间测成了服务端延迟**
这也解释了之前所有的怪象：
  - 点赞路径 45ms 的"地板" —— 是客户端开销
  - RPS 随并发上升反而下降 —— 并发越高，客户端事件循环越忙，每个连接的服务越慢
  - like-status 在 c=5（CPU 57%，没饱和）时平均延迟 19ms —— 这才是真实服务端延迟的量级，而且 19ms里可能还带着客户端开销
# 更换测压工具: wrk
## 测试:
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
## **SQLite 非 WAL 模式下，写事务锁住整个数据库文件，连 SELECT 都被阻塞**
绝大多数请求很快，一小撮请求卡到天荒地老: *典型的锁竞争*
51 RPS + 256 个超时 + 153 个 500，这就是 SQLite 的真实天花板
**修法：WAL + busy_timeout，一个共享 engine 工厂: @app/core/database.py 16~32**

## 纯框架:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/**
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
## 一次sql查询:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency http://127.0.0.1:8858/health/db**
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
## 点赞接口:**./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like**
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

## 结论
**这才是真正的数据**
**纯框架：6529 RPS**: *这是上限。FastAPI + Uvicorn，本地回环，-c50，什么业务逻辑都没有，就是路由 + 序列化 + 返回*

**一次 SQL 查询**：1288 RPS
RPS 从 6529 → 1288，掉了 5 倍；p50 从 6.67ms → 34.74ms，慢了 5 倍。
这两个 5 倍是同一件事：每次请求多了一次 SQL 查询，整个链路被拉长了 5 倍

