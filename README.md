# Holocron Blog

一个基于 FastAPI 与 Vue 3 的内容论坛，用户可以发布主题、参与评论、点赞互动并接收通知，同时提供分类、标签、个人主页和后台管理功能。

## 技术栈

- 后端：FastAPI、Pydantic v2、SQLAlchemy 2.0（异步）
- 数据库：SQLite（默认）或 PostgreSQL
- 缓存与消息：Redis
- 认证：JWT
- 前端：Vue 3、Vue Router、Vite
- 部署：Docker Compose、Nginx

## 快速开始

### Docker Compose

```bash
docker compose up --build
```

启动后访问：

- 论坛：`http://localhost`
- API 文档：`http://localhost:8848/docs`
- API 健康检查：`http://localhost:8848/health/db`

首次启动或数据库结构更新后执行迁移：

```bash
docker compose exec api alembic upgrade head
```

### 本地开发

要求：Python 3.11+、Node.js 18+、Redis。

后端：

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8848
```

前端：

```bash
cd frontend
npm install
npm run dev
```

开发地址：

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8848/docs`

### 本地与 Docker 数据库

本地命令默认使用根目录的 `holocron.db`，Docker API 使用宿主机 `data/holocron.db`（容器内为 `/app/data/holocron.db`）。两套数据库相互独立，需要分别迁移和初始化：

```bash
alembic upgrade head                                      # 本地数据库
python -m scripts.create_admin                            # 本地管理员
docker compose exec api alembic upgrade head              # Docker 数据库
docker compose exec api python scripts/create_admin.py     # Docker 管理员
```

管理员脚本可重复执行，默认账号为 `admin`，密码为 `admin123`。仅用于开发环境。

## 环境变量

项目会读取根目录下的 `.env`。本地开发可使用默认配置；生产环境至少应设置安全的 `SECRET_KEY`。

```env
DATABASE_URL=sqlite+aiosqlite:///./holocron.db
SECRET_KEY=replace-with-a-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_HOST=localhost
REDIS_PORT=6379
RATE_LIMIT_ENABLED=true
BACKGROUND_TASKS_ENABLED=true
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173,http://localhost:8848
TIMEZONE=Asia/Shanghai
```

使用 PostgreSQL 时可传入 `postgresql://...` 连接串，应用会自动切换到异步驱动。PostgreSQL 环境禁止使用默认 `SECRET_KEY`。

仅在本地缓存压测时，关闭限流、同步请求日志和进程内后台任务。多 worker 模式不能与 `--reload` 同时使用：

```bash
RATE_LIMIT_ENABLED=false \
BACKGROUND_TASKS_ENABLED=false \
LOG_LEVEL=WARNING \
uvicorn app.main:app --host 127.0.0.1 --port 8848 --workers 4 --no-access-log
```

自动并发阶梯压测会依次测试 10、25、50、100、200 并发，每档执行 3 轮并取中位数：

```bash
python scripts/benchwork_cache_governance.py \
  --requests 1000 \
  --rounds 3 \
  --output cache-concurrency-report.md
```

报告会列出每档的 RPS、平均延迟、p95、p99、成功率，并自动标记峰值并发。建立基线后可通过 `--min-peak-rps` 和 `--max-p95-ms` 让性能退化直接返回非零退出码。

## 常用命令

```bash
pytest                         # 后端测试
pytest --cov=app               # 后端测试与覆盖率
alembic upgrade head           # 应用数据库迁移
cd frontend && npm run build   # 构建前端
```

## 项目结构

```text
app/
├── routers/       # API 路由
├── services/      # 业务逻辑
├── models/        # SQLAlchemy 模型
├── schemas/       # Pydantic 数据模式
├── core/          # 配置、数据库、认证与 Redis
└── middleware/    # 中间件
frontend/src/      # Vue 前端源码
test/              # pytest 测试
alembic/versions/  # 数据库迁移
```

## API

主要接口包括：

- `/api/v1`：注册、登录和 Token 刷新
- `/articles`：主题发布、浏览与点赞
- `/categories`、`/tags`：分类与标签
- `/comments`：主题讨论与评论互动
- `/notifications`：通知与 WebSocket
- `/admin`：用户管理

完整请求参数和响应结构以运行中的 Swagger 文档 `/docs` 为准。
