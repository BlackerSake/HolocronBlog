# This is my blog - Holocron Blog

  基于 FastAPI 的个人博客系统，支持文章管理、分类、标签、Markdown 渲染、JWT 认证。

## 技术栈

- **后端框架**: FastAPI + Pydantic v2
- **ORM**: SQLAlchemy 2.0 (async)
- **数据库**: SQLite (开发阶段)
- **认证**: JWT (python-jose + bcrypt)
- **Markdown**: mistune

## 运行

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8848
```
```bash
npm run dev
```
## API 端点

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/register` | 注册 |
| POST | `/api/v1/login` | 登录，返回 JWT Token |

### 用户

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/users/me` | 获取当前用户信息 * |

### 文章

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/articles` | 文章列表（支持分页、分类、标签、搜索筛选） |
| GET | `/articles/{slug}` | 文章详情 |
| POST | `/articles` | 创建文章 * |
| PUT | `/articles/{slug}` | 更新文章 * |
| DELETE | `/articles/{slug}` | 软删除文章 * |

### 分类

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/categories` | 分类列表 |
| POST | `/categories` | 创建分类 * |
| PUT | `/categories/{item_id}` | 更新分类 * |
| DELETE | `/categories/{item_id}` | 删除分类 * |

### 标签

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tags` | 标签列表 |
| POST | `/tags` | 创建标签 * |
| PUT | `/tags/{item_id}` | 更新标签 * |
| DELETE | `/tags/{item_id}` | 删除标签 * |

> `*` 需要认证，请求头带 `Authorization: Bearer <token>`。分类和标签需 admin 角色；文章需作者或 admin。



## 环境变量

创建 `.env` 文件（可选，已有默认值）：

```env
DATABASE_URL=sqlite+aiosqlite:///./holocorn.db
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
```
