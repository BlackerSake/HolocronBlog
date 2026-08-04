# 点赞热 Key 并发压测报告

- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮，取中位数
- 模型：单用户、单文章热 Key，关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 256.18 | 38.78 | 50.74 | 84.50 | 100.00% | `{200: 3000}` |
| 25 | 188.89 | 130.41 | 252.21 | 379.72 | 100.00% | `{200: 3000}` |
| 50 | 148.01 | 323.96 | 913.72 | 1342.60 | 100.00% | `{200: 3000}` |
| 100 | 142.10 | 646.06 | 1834.44 | 2746.56 | 99.97% | `{200: 2999, 'ReadError': 1}` |
| 200 | 114.89 | 1577.85 | 4409.09 | 7551.24 | 100.00% | `{200: 3000}` |

- 压测后点赞状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 2, 'is_liked': True}`

## 测试环境

- 日期：2026-08-04
- API：单个 Uvicorn worker，关闭接口限流
- 数据库：本机 SQLite 临时副本
- Redis：本机 Docker `redis:alpine` 临时容器
- 负载：单用户反复向同一文章提交 `is_liked=true/false`，属于热 Key 竞争测试
- 入口阶梯压测期间关闭 Stream Worker，随后分别测试积压追平和 Worker 在线场景

## 与优化前对比

| 并发 | 优化前 RPS | 优化后 RPS | 吞吐提升 | 优化前 p95 | 优化后 p95 | p95 降低 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 67.49 | 256.18 | 3.80 倍 | 215.51 ms | 50.74 ms | 76.5% |
| 25 | 62.83 | 188.89 | 3.01 倍 | 710.51 ms | 252.21 ms | 64.5% |
| 50 | 71.28 | 148.01 | 2.08 倍 | 1756.37 ms | 913.72 ms | 48.0% |
| 100 | 52.86 | 142.10 | 2.69 倍 | 4810.72 ms | 1834.44 ms | 61.9% |
| 200 | 43.37 | 114.89 | 2.65 倍 | 11303.16 ms | 4409.09 ms | 61.0% |

10 并发下吞吐量由 67.49 RPS 提升至 256.18 RPS，约为原来的 3.80 倍；p95 由 215.51 ms 降至 50.74 ms。100 并发出现 1 次客户端 `ReadError`，因此不把高并发档作为稳定性能指标。

## Stream 弛峰落库

- 入口阶梯压测后待消费事件：8599 条
- Worker 追平时间：49.722 秒
- 平均处理速度：约 172.95 条/秒
- 消费完成状态：`lag=0`、`pending=0`
- Redis 最终状态：文章点赞数 2，点赞用户为 2、3
- SQLite 最终状态：文章 `like_count=2`，点赞明细用户为 2、3
- 与优化前 15767 条 Stream 事件相比，本轮事件量减少约 45.5%，说明相同状态请求不会重复写入 Stream

事件总量下降明显，但 SQLite Worker 的单条消费速度没有提升。因此当前持久化瓶颈仍在 SQLite 串行写入，而不是 Redis Lua。

## Worker 在线对照

独立 Worker 在线时，以 10 并发执行 1000 个请求：

- RPS：226.07
- 平均延迟：43.90 ms
- p95：77.02 ms
- p99：114.16 ms
- 成功率：100%
- 测试结束后：`lag=0`、`pending=0`，Redis 与 SQLite 最终状态一致

Worker 在消费完成后的下一次阻塞读取中触发 Redis `TimeoutError` 并退出。该问题不影响本轮已完成数据的一致性，但生产部署前应修复消费者的空闲超时处理，否则长期运行可靠性不足。

## 复现步骤

```bash
# 1. 启动隔离 Redis
docker run --rm -d --name holocron-like-bench-redis -p 6389:6379 redis:alpine

# 2. 复制数据库，避免污染开发数据
cp holocron.db /tmp/holocron-like-bench-v2.db

# 3. 启动 API，入口阶梯压测时关闭后台任务
DATABASE_URL=sqlite+aiosqlite:////tmp/holocron-like-bench-v2.db \
REDIS_PORT=6389 \
RATE_LIMIT_ENABLED=false \
BACKGROUND_TASKS_ENABLED=false \
LOG_LEVEL=CRITICAL \
uvicorn app.main:app --host 127.0.0.1 --port 8858 --no-access-log --log-level critical

# 4. 执行阶梯压测
python scripts/benchwork_likes.py \
  --base-url http://127.0.0.1:8858 \
  --slug 1111 \
  --username benchuser \
  --password Benchpass123 \
  --requests 1000 \
  --rounds 3 \
  --output like-concurrency-report-v2.md

# 5. 启动 Stream Worker，观察积压追平
DATABASE_URL=sqlite+aiosqlite:////tmp/holocron-like-bench-v2.db \
REDIS_PORT=6389 \
LOG_LEVEL=ERROR \
python -m app.core.like_stream

# 6. 查看消费者组状态；lag 与 pending 均应为 0
docker exec holocron-like-bench-redis redis-cli XINFO GROUPS like:events
```

## 结论

当前单机、单 Uvicorn worker、SQLite 环境下，建议把 **10 并发、256.18 RPS、p95 50.74 ms、成功率 100%** 作为入口链路的稳定测试结果。25 并发仍保持 100% 成功，但 p95 上升至 252.21 ms；继续提高并发只会增加排队延迟。该结果证明本次幂等状态写入、轻量目标查询和去除同步数据库写入有效，但不能代表 Redis 或生产 PostgreSQL 环境的理论上限。
