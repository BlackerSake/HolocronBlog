# 点赞热 Key 并发压测报告

- 目标：`http://127.0.0.1:8858/articles/1111/like`
- 每档：`1000` 请求 × `3` 轮，取中位数
- 模型：单用户、单文章热 Key，关闭接口限流

| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |
|---:|---:|---:|---:|---:|---:|:---|
| 10 | 67.49 | 147.52 | 215.51 | 243.35 | 100.00% | `{200: 3000}` |
| 25 | 62.83 | 391.20 | 710.51 | 928.36 | 100.00% | `{200: 3000}` |
| 50 | 71.28 | 681.87 | 1756.37 | 2680.41 | 99.90% | `{200: 2997, 'ReadError': 1, 'RemoteProtocolError': 2}` |
| 100 | 52.86 | 1776.92 | 4810.72 | 6866.46 | 100.00% | `{200: 3000}` |
| 200 | 43.37 | 4174.43 | 11303.16 | 16394.60 | 100.00% | `{200: 3000}` |

- 入口压测结束、Worker 消费前的 Redis 状态：`{'target_type': 'article', 'target_id': 1, 'like_count': 2, 'is_liked': True}`

## 测试环境

- 日期：2026-07-18
- API：单个 Uvicorn worker，FastAPI，关闭接口限流
- 数据库：本机 SQLite 临时副本
- Redis：本机 Docker `redis:alpine`，独立临时容器
- 客户端、API、SQLite、Redis 位于同一台开发机
- 负载：单用户反复切换同一篇文章，属于热 Key 竞争测试
- 入口压测期间暂停 Stream Worker，避免 SQLite 读写锁干扰请求入口；随后单独启动 Worker 测量积压追平速度

## Redis 原始对照

| 场景 | 并发 | 请求数 | 吞吐量 | p50 |
|:---|---:|---:|---:|---:|
| Redis SET | 50 | 100000 | 87565.68 RPS | 0.295 ms |
| Redis GET | 50 | 100000 | 60864.27 RPS | 0.447 ms |
| 项目点赞 Lua（含 Set 切换、计数更新、XADD） | 50 | 100000 | 29691.21 RPS | 1.351 ms |

## Stream 落库

- 待消费事件：15767 条
- Worker 追平时间：46.593 秒
- 平均处理速度：338.40 条/秒
- 消费完成状态：`lag=0`、`pending=0`
- Redis 最终状态：文章点赞数 2，点赞用户为 2、3
- SQLite 最终状态：文章 `like_count=2`，点赞明细用户为 2、3
- 结论：本轮最终状态一致

## Worker 在线对照

独立 Worker 在线、SQLite 同时读写时，以 10 并发执行 100 个请求：

- RPS：26.94
- 平均延迟：357.77 ms
- p95：564.27 ms
- p99：639.27 ms
- 成功率：100%

该结果主要反映 SQLite 单写锁和同机资源竞争，不代表 Redis 或 PostgreSQL 部署下的上限。

## 压测发现并修复的问题

1. Redis 成功后请求仍同步写数据库，同时 Stream Worker 再次落库，导致唯一键冲突和 SQLite 锁竞争；已删除重复同步写库路径。
2. Consumer Group 首次创建使用 `$` 会跳过创建前积压；已改为从 `0` 开始，确保 Worker 恢复时可以追平历史事件。
3. 50 并发入口测试出现 3 次客户端连接错误，且 50 并发后延迟明显上升；当前单 worker + SQLite 环境建议以 10–25 并发作为稳定区间，需要 PostgreSQL、多 worker 和独立压测机后再评估生产上限。

## 复现步骤

```bash
# 1. 启动独立 Redis

docker run --rm -d --name holocron-like-bench-redis -p 6389:6379 redis:alpine

# 2. 使用临时数据库启动 API；入口吞吐测试时暂停后台 Worker

DATABASE_URL=sqlite+aiosqlite:////tmp/holocron-like-bench.db \
REDIS_PORT=6389 \
RATE_LIMIT_ENABLED=false \
BACKGROUND_TASKS_ENABLED=false \
uvicorn app.main:app --host 127.0.0.1 --port 8858 --no-access-log

# 3. 执行点赞入口阶梯压测

python scripts/benchwork_likes.py \
  --requests 1000 \
  --rounds 3 \
  --output like-concurrency-report.md

# 4. 启动独立 Stream Worker，等待 lag 归零

DATABASE_URL=sqlite+aiosqlite:////tmp/holocron-like-bench.db \
REDIS_PORT=6389 \
python -m app.core.like_stream

# 5. 查看消费状态

docker exec holocron-like-bench-redis \
  redis-cli XINFO GROUPS like:events
```

## 简历可用结论

在本机单 Uvicorn worker、SQLite、单用户单文章热 Key 条件下，点赞入口在 10 并发时达到 67.49 RPS、p95 215.51 ms、成功率 100%；Redis 侧实际点赞 Lua 达到 29691.21 RPS，证明当前主要瓶颈位于完整 HTTP/ORM 链路而非 Redis。Redis Stream Worker 可按约 338 条/秒追平 SQLite 落库，并在消费结束后保持 Redis 与数据库点赞状态一致。
