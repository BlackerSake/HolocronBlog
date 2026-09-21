# Holocron Blog 全程复盘：从设计到部署(AI整理)

> 复盘范围：`2a62b3d`（2026-06-24）→ `7145e3d`（2026-09-17），共 **67 个提交**，跨度近 3 个月。
> 本文逐条罗列，**不做提炼**，保留文件名、函数名、错误信息、性能数字，方便回忆。
> 唯一作者：`J0hnnyPoter <lp9952@qq.com>`（另有 GitHub 网页提交身份 `J0hnny Poter / BlackerSake`，见 `bd4c378`）。

---

## 0. 总览

### 0.1 项目形态的变迁

| 阶段 | 时间 | 形态 |
|---|---|---|
| A | 06-24 ~ 06-30 | 个人博客骨架：认证、文章、分类标签、评论 |
| B | 07-02 ~ 07-14 | 管理后台、通知/WebSocket、点赞、缓存与消息队列（复杂度爆发期） |
| C | 07-16 ~ 08-04 | 博客 → 内容论坛叙事转向、压测驱动、点赞幂等化 |
| D | 09-10 ~ 09-17 | SQLite → PostgreSQL、云部署适配（Vercel/Render/Upstash） |

### 0.2 版本号轨迹

`0.0.1` → `0.2.0`（31a34fe，前端落地） → `0.2.1`（e1226b6） → `0.3.0`（aebf0dd，CI） → `0.4.0`（5e65ea3，浏览量） → `0.5.0`（d44fa59，服务层抽取）→ 之后固定在 `0.5.0`

标签：`v0.2.1`、`v0.4.1`、`v0.5.1`（分支只有 `main`）

### 0.3 提交规模 TOP 5

| 提交 | 规模 | 内容 |
|---|---|---|
| `31a34fe` | 31 文件 +3538 | 整个 Vue3 前端 + nginx + log_call |
| `710a17c` | 19 文件 +1461 | 评论点赞 + likes 表主键重建 |
| `c7eaad0` | 17 文件 +1385 | 全套集成测试 |
| `d44fa59` | 18 文件 +1305/-704 | 服务层抽取，删 `/users/me` |
| `ddcb0c1` | 19 文件 +1051/-1172 | 普通用户发帖权限 + 论坛化前端 |

---

## 1. 全程时间线（逐提交）

### 阶段 A：从零到"能跑"（06-24 ~ 06-30，22 个提交）

| 日期 | hash | 内容 |
|---|---|---|
| 06-24 12:06 | `2a62b3d` | 基础结构：config / main / CORS / requirements |
| 06-24 15:52 | `6ccc4cf` | Alembic + 用户注册 + 异步引擎 + create_admin 脚本 |
| 06-24 17:05 | `a2bfb44` | OAuth2 登录 + JWT + `UserRole` 枚举 |
| 06-24 18:52 | `ba7dd10` | 移除 ZoneInfo 改 UTC；建 categories/tags 路由 |
| 06-25 16:59 | `0be9a2d` | 文章 CRUD、`article_tags`、CRUD 路由工厂、slugify |
| 06-25 17:10 | `5089d1f` | **统一 `Response<T>` + 全局异常处理器** |
| 06-25 17:56 | `33f8ad8` | README / Dockerfile / docker-compose |
| 06-25 18:17 | `4c5bc78` | PG URL 自动转 asyncpg；`holocorn.db` → `holocron.db` |
| 06-26 11:48 | `31a34fe` | **前端整体落地** + `@log_call` + slugify 中文修复 |
| 06-26 17:13 | `e1226b6` | 邮箱可选、admin→backend 改名、取消发布 |
| 06-27 13:58 | `c7eaad0` | 全套测试；**修 JWT exp 缩进 bug** |
| 06-27 14:19 | `aebf0dd` | GitHub Actions 测试工作流；`.coverage` 入库 |
| 06-27 14:22 | `580113a` | requirements 误删（-39 行） |
| 06-27 14:27 | `b953942` | 5 分钟后加回来（+22 行） |
| 06-27 14:30 | `bd4c378` | 日志路径改动态（顺带删掉 makedirs） |
| 06-27 17:39 | `5e65ea3` | **接入 Redis**：浏览量 INCR + 热门文章 + 限流中间件 |
| 06-27 17:41 | `fa41433` | 补回 `os.makedirs` |
| 06-27 18:02 | `ba7644c` | Redis 三处 try/except 降级 |
| 06-29 14:00 | `95ed934` | Comment 模型 + 树形构建 + 软删除 |
| 06-29 18:35 | `d44fa59` | 文章服务层抽取；删 `/api/v1/users/me`（BREAKING） |
| 06-29 20:02 | `b725acb` | 评论前端组件 + nginx 分流 |
| 06-30 09:17 | `27d42d1` | 评论回复聚焦；前端 `d += "Z"` 时区 hack |
| 06-30 10:25 | `4a46d1c` | **时区又加回来**：`TIMEZONE` + `tz` property |

### 阶段 B：复杂度爆发（07-02 ~ 07-14，26 个提交）

| 日期 | hash | 内容 |
|---|---|---|
| 07-02 13:02 | `2449039` | 用户管理、角色软保护、permission_service 缓存 |
| 07-02 14:56 | `3c4a54a` | 登录返回用户信息、Toast/Confirm 组件、顶部导航 |
| 07-02 16:47 | `6715946` | 头像首字母 |
| 07-02 16:52 | `378ca2c` | **conftest 补路由命名空间 mock** |
| 07-03 16:16 | `673c713` | 通知模型/服务/路由 + `ConnectionManager`（先建不接线） |
| 07-03 16:21 | `b1f8bc5` | 补 `broadcast:create` 权限（1 行） |
| 07-03 16:57 | `02ea795` | 评论通知 + **前端 30 秒轮询** |
| 07-06 10:15 | `f6882cb` | refresh token、SECRET_KEY 生产校验、CORS 环境变量化 |
| 07-06 13:44 | `2780959` | 用户资料字段、**alembic destructive 防护**、seed 角色 |
| 07-07 10:52 | `3a5e88e` | likes 表（**复合主键**）+ `nick_name`→`nickname` |
| 07-07 15:36 | `710a17c` | 评论点赞 + **likes 主键重建迁移** |
| 07-08 11:40 | `fcdde7e` | 全量 docstring + 类型注解（32 文件） |
| 07-08 17:32 | `273c2c6` | **点赞 Redis 化：Lua 原子切换 + 分布式锁 + 降级** |
| 07-09 02:38 | `fd0688e` | **Redis Stream 异步落库** |
| 07-10 23:44 | `c850b09` | 滑动窗口限流、熔断器、死信队列、独立消费者进程 |
| 07-12 00:53 | `36d9462` | 令牌桶限流 + **Pub/Sub 预热替代自旋** + nginx 限流 |
| 07-12 23:43 | `9311e2e` | 文章详情 Cache-Aside + 后台重建 + Redis AOF |
| 07-13 18:02 | `9f57f02` | 缓存一致性对账 + **ZSet 热度榜**；修 `view_count` 字段错 |
| 07-14 14:47 | `6b45704` | 修对账缩进 bug + FakeRedis 增强 |
| 07-14 15:51 | `95d7ba5` | 前端热榜、编辑器实时预览、nginx `brust` 修复 |
| 07-14 23:44 | `ddcb0c1` | 普通用户发帖权限 + `reply_count` + 论坛化前端改名 |
| 07-16 11:54 | `f21ecdc` | WebSocket 多标签页 + 同源检查；**修 start/stop 复制粘贴错** |

### 阶段 C：转向与瘦身（07-16 ~ 08-04，3 个提交）

| 日期 | hash | 内容 |
|---|---|---|
| 07-17 17:17 | `89513e4` | README 论坛化叙事、`asyncio.gather`、压测脚本体系、WS token 过期检查 |
| 08-01 08:53 | `ef1a039` | **`LIKE_GROUP_START_ID` 由 `$` 改 `0`**；删请求路径同步写库 |
| 08-04 16:06 | `59e26a3` | **toggle(POST) → 幂等 PUT**、`changed` 贯穿全链路、`SCARD` 为权威计数 |

### 阶段 D：上生产（09-10 ~ 09-17，15 个提交）

| 日期 | hash | 内容 |
|---|---|---|
| 09-10 15:08 | `d7111e9` | **SQLite WAL + synchronous=NORMAL + timeout=30**、统一 `create_engine` |
| 09-10 16:50 | `e52ced4` | 用户认证缓存（60s TTL）、文章点赞目标缓存、修 DetachedInstanceError |
| 09-10 17:06 | `8da7481` | **修 redis-py 8.0 `socket_timeout` 雪崩**；`RedisTimeoutError` 兜底 |
| 09-13 14:04 | `dada73a` | **PG 命名约束 DuplicateTable**：改迁移时序 |
| 09-13 16:05 | `0e36165` | 通知流异步化（RPS ×1.73、p99 −40%） |
| 09-13 18:11 | `ca49ed9` | 缓存命中统计 `_cache_stats`；压测清 Redis 后 sleep 30s |
| 09-14 10:45 | `e09cc4e` | **时区第三轮：回到 UTC**（BREAKING） |
| 09-14 14:40 | `bcd1854` | 迁移 PostgreSQL、UTC 时间戳迁移脚本、NOGROUP 处理 |
| 09-17 09:23 | `eb5a319` | README 补高并发设计说明 |
| 09-17 10:09 | `07edfc0` | Vercel 环境跳过文件日志；`--no-access-log` |
| 09-17 10:24 | `117215f` | CI 加环境变量 |
| 09-17 10:32 | `0e2b50d` | 日志模块重构（删重复导入） |
| 09-17 11:19 | `d79d931` | `PORT` 环境变量、**alembic 改异步引擎**、RENDER 检测 |
| 09-17 12:28 | `a50bbdd` | Upstash Redis 支持 |
| 09-17 12:39 | `cf653e3` | `UPSTASH_REDIS_REST_URL` → `REDIS_URL` |
| 09-17 12:45 | `7c0757a` | 修日志条件 **`or` → `and`**（De Morgan 写反） |
| 09-17 13:05 | `7145e3d` | `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` |

---

## 2. 踩坑全记录

### 2.1 时区：三轮横跳（最典型的反复）

**第一轮（06-24）硬编码上海时区**
- `a2bfb44` 的 `app/core/security.py`：`expire = datetime.now(ZoneInfo("Asia/Shanghai")) + expires_delta`
- `6ccc4cf` 的 `app/models/user.py`：`default=lambda: datetime.now(ZoneInfo("Asia/Shanghai"))`
- 顺带埋雷：注释写"默认过期时间 300s"，实际配置是 30 分钟，单位注释一直错。

**第二轮（06-24 18:52）砍掉 ZoneInfo 换 UTC**
`ba7dd10` 把 security / user 改为 `datetime.now(timezone.utc)`，`from zoneinfo import ZoneInfo` 删除。但只改了这两个文件；`0be9a2d` 新建的 Article 继承 UTC，`4c5bc78` 才补上 `DateTime(timezone=True)`；Category/Tag 仍是 `server_default=func.now()`（数据库本地时间）——**口径从这时起就不统一了**。

**前端被迫打补丁（06-29 ~ 06-30）**
后端存 UTC 但序列化出的 ISO 字符串**不带时区后缀**（naive），浏览器 `new Date()` 按本地时间解析 → 显示差 8 小时。
- `b725acb`：Home.vue / ArticleDetail.vue 加 `toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })`
- `27d42d1`：在 6 个 .vue 文件里加 hack：

```javascript
function formatTime(d) {
  if (!d.endsWith("Z") && !d.includes("+")) d += "Z"   // 先按 UTC 解析
  ...
```

  注意这行写在 `if (!d) return ''` **之前**——`d` 为 null 会 TypeError，守卫顺序 bug 跟着 hack 一起留下。

**第三轮（06-30 10:25）又加回来**
`4a46d1c` 在 config 里加 `TIMEZONE = "Asia/Shanghai"` 和 `tz` property，`security.py` 改回 `datetime.now(settings.tz)`，**5 个模型全部**换成 `settings.tz`，前端 6 个文件的 `d += "Z"` 又逐个删掉。同时 Category/Tag 从 `server_default=func.now()`（DB 时间）改成 Python 侧 `default=lambda:`——行为变了，且这两列**没有** `DateTime(timezone=True)`，与 article/comment 又不一致。

**第四轮（09-14）终局回到 UTC**
`e09cc4e` 把 `settings.tz` 全部换回 `timezone.utc`，12 文件，标 BREAKING。`bcd1854` 又补了一个 `3d1e7f9a2b4c_use_utc_timestamps.py` 迁移把时间戳改成带时区感知。

**遗留**：`app/core/config.py` 里的 `TIMEZONE` 与 `tz` property 现在**无人使用**（grep 全仓库 0 命中），是死配置。

> 根因：始终没有定下"**存储用 UTC、展示用时区**"这条准则，于是每次"哪边显示错"就去改另一边。

### 2.2 JWT 的 `exp` 缩进 bug（`a2bfb44` 埋，`c7eaad0` 修，存活 3 天）

```python
if expires_delta:
    expire = datetime.now(...) + expires_delta
else:
    expire = datetime.now(...) + timedelta(minutes=...)
    to_encode.update({"exp": expire})          # ← 多缩进了一层
    encoded_jwt = jwt.encode(...)              # ← 同样在 else 里
    return encoded_jwt
```

后果：**显式传 `expires_delta` 的调用路径不设置 exp 且返回 `None`**。`c7eaad0` 才把这四行 dedent 出来。

### 2.3 bcrypt 72 字节截断：变量算了但没用（`6ccc4cf` 埋，`a2bfb44` 修）

```python
# 防御性截断到 72 字节（UTF-8）
password_bytes = password.encode("utf-8")[:72]
return pwd_context.hash(password)      # ← 用的是原变量，截断白写
```

**残留**：`api/v1/endpoints/auth.py` 的 `hash_password` 与 `core/security.py` 的 `get_password_hash` 两套并存；`c7eaad0` 只给后者加了 NFC 归一化和长度校验（`<8` / `>72` 字节抛 ValueError），**注册路径用的仍是前者**，校验没覆盖注册口。

### 2.4 依赖管理：误删 → 5 分钟后急救（`aebf0dd` → `580113a` → `b953942`，8 分钟内三次翻转）

- `aebf0dd`（14:19）把 requirements 换成 pip freeze 全量清单（53 行，含大量间接依赖）。
- `580113a`（14:22）"清理"到 12 行，删掉的都是真依赖：`aiosqlite`（默认 SQLite 驱动）、`alembic`（迁移）、`bcrypt`、`python-multipart`（`OAuth2PasswordRequestForm` 硬依赖）、`email-validator`（`EmailStr` 硬依赖）、`python-dotenv`、`pytest-cov`、`coverage`。同时删掉了形如 `packaging @ file:///home/conda/feedstock_root/...` 的本地路径包（这个删得对）。
- `b953942`（14:27）全部加回，并把刚"升级"的 `fastapi 0.138.1` **降回 0.138.0**；顺手加入 `pipreqs`、`requests`、`beautifulsoup4`——代码从未 import，纯噪音。
- 净效果：8 分钟内依赖先升后降、先删后加。

> 根因：没有"直接依赖 vs 间接依赖"分层，没有 requirements-dev / lock 概念。

### 2.5 日志目录：4 个提交才稳定（`6ccc4cf` → `bd4c378` → `fa41433` → 阶段 D 重写）

- `6ccc4cf`：`log_dir = "/Alpha/College_new/HolocronBlog/logs"`（**硬编码绝对路径**），且 `os.makedirs(log_dir)` 建的是绝对路径，而 `FileHandler("logs/app.log")` 用的是相对 cwd 路径——cwd 不对就 `FileNotFoundError`。
- `bd4c378`（GitHub 网页提交）：改成 `os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")`，**但把 `os.makedirs` 连同判断一起删了**——logs/ 不存在时 import main.py 直接炸，应用起不来。
- `fa41433`（3 小时后）：补回一行 `os.makedirs(log_dir, exist_ok=True)`。
- `07edfc0`（09-17）：加 `if not os.getenv("VERCEL")` 条件 + `handlers = [logging.StreamHandler(sys.stdout)]`；同一提交 `import os` 重复导入（`0e2b50d` 才清掉）。
- `7c0757a`：把条件从 `if not os.getenv("VERCEL") or not os.getenv("RENDER")` 改成 `... and not ...`——**`or` 写反导致"只要不是 Vercel 就写文件"，在 Render 上照样建日志文件**，且无论哪个环境都会尝试 `os.makedirs("logs")`。

### 2.6 422 状态码常量用错（`5089d1f` 埋，`e1226b6` 修）

`app/core/exceptions.py` 用了 `status.HTTP_422_UNPROCESSABLE_ENTITY`，`e1226b6` 改为 `HTTP_422_UNPROCESSABLE_CONTENT`，同时补了异常日志：`logger.warning("%s %s → %s", request.method, request.url.path, exc.detail)`。
**同文件未修**：`global_exception_handler` 里 `detail=str(exc)` 把内部异常原文回给客户端（信息泄漏），注释自己写了"生产环境最好记日志"但没做。

### 2.7 统一 `Response<T>` 的不兼容面（`5089d1f`）

约定发布后出现的所有摩擦：
1. **前端必须 unwrap**：`31a34fe` 的 `frontend/src/api/index.js` 写了 `function unwrap(res)`，`if (body.code && body.code >= 400) throw new Error(...)`，返回 `body.data`。
2. **新端点漏网**：`95ed934` 的评论路由 `response_model=CommentOut` / `return comment` 没包装，`b725acb` 当晚才发现并改成 `Response[CommentOut]`；测试断言到 `27d42d1` 才跟上（`resp.json()["content"]` → `resp.json()["data"]["content"]`）。**"统一约定"发布 4 天后仍有漏网端点**。
3. **204 无法包装**：`delete_article` 等用 `status_code=204 + return None`，永远是不一致的例外。
4. **`/users/me` 加-删-删链**：`e1226b6` 前端加 `authAPI.me`（`useAuth.js` 里甚至留了注释 `// ponytail: no dedicated user-fetch endpoint on backend, rely on login data`），`d44fa59` 后端把端点删掉（BREAKING），`b725acb` 前端再删回去。3 天。
5. **`f6882cb` 才补上两个漏网**：`/unread_count` 没套 `Response[...]`（前端 `unwrap` 拿不到 `.data`），`mark_notification_read` **根本没有 return 语句**。

### 2.8 草稿泄露窗口（`31a34fe` 造成，`e1226b6` 补）

`31a34fe` 把 `get_article` 从 `get_published_article_by_slug` 改成走不限发布状态的 `get_article_by_slug` → **未发布文章可被公开读取**。e1226b6 合并两个近似函数为 `_get_article_by_slug`，并在前台调用侧补：

```python
article = await _get_article_by_slug(db, slug)
if not article or not article.is_published: # 防御措施
    raise HTTPException(404, "文章不存在")
```

即：**把"由 SQL 过滤"的约束挪到了"靠调用侧自觉"的规矩层**。

### 2.9 标签筛选的笛卡尔积（`0be9a2d` 埋，长期未修）

```python
if tag_id:
    query = query.where(Tag.id == tag_id)   # 没有 join article_tags
```

生成 `FROM articles, tags`，只要库里有该 id 的标签，**所有文章都命中**。

### 2.10 slugify 中文被剥光（`0be9a2d` 埋，`31a34fe` 修）

```python
# FIXME 中文被完全剥离, 需要重写
def slugify(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    ...
    return text
    """效果："Hello 世界, 你好!" → "hello-" ..."""   # return 之后的死 docstring
```

`31a34fe` 改为 `re.sub(r'[^a-z0-9一-鿿]+', '-', text).strip('-')` + `or 'untitled'` 兜底。
**残留**：`slug` 列没有 unique 约束；`update_article` 里 `article.slug = slugify(title)` 不查冲突，改名会撞 slug。

### 2.11 Redis 裸调用 → 20 分钟后连夜补降级（`5e65ea3` → `ba7644c`）

`5e65ea3`（17:39）接入 Redis 时全部裸调（详情页 `incr`、`/hot` 的 `get`/`set`），**本机没起 Redis 就是 500**。`ba7644c`（18:02）给三处裹上 `try/except Exception: pass`。
同提交的测试改动：`test/conftest.py` 里

```python
# 测试环境下移除限流中间件，避免跨测试累计计数器或依赖 Redis
app.user_middleware = [mw for mw in app.user_middleware if mw.cls is not BaseHTTPMiddleware]
```

按 `mw.cls is not BaseHTTPMiddleware` 过滤等于**把所有 BaseHTTPMiddleware 一律剥掉**（当前只有一个所以没炸）。
另外 `reset_db` 的 docstring 改成"重建所有表**并重置限流计数器**"，但代码里没有任何重置计数器的语句——**注释撒谎**。

### 2.12 前端 401 拦截器误伤登录页（`31a34fe` 埋，`e1226b6` 修）

任何 401 都 `localStorage.removeItem(...)` + `window.location.href = '/login'` → 密码错误时用户看不到"密码错误"提示，直接被硬跳转。
`e1226b6` 补：`if (status === 401 && !err.config.url.includes('/login'))`。
`95d7ba5` 又补空指针：`err.config?.url?.includes('/login')`（网络层错误没有 `url`，会再抛 TypeError 吞掉原始错误）。

### 2.13 评论树三次返工（`95ed934` → `d44fa59` → `27d42d1`）

1. `95ed934`：`async def build_comment_tree(...)` **全文没有 await 也无 IO**，硬挂 async；`Comment.is_published` 字段意义未明（`CommentOut` 里注释 `# 默认为编辑` 还写反了）；POST `return comment` 但 `CommentOut` 含 `author: UserOut`，而刚 commit 的 ORM 对象关系未加载 → 异步懒加载失败。
2. `b725acb`：补创建后 `select(...).options(joinedload(Comment.author))`；`d44fa59` 又在模型上加 `author` relationship；路由函数从 `create_comment` 改名 `create_comment_post`（原名与 `from app.services.comment_service import create_comment` **撞名遮蔽**）。
3. `d44fa59` 把 `build_comment_tree` 从 async 改回同步。
4. `27d42d1`：后端费 147 行做的嵌套树，被 `CommentSection.vue` 一段"**打平到第二层**"的 JS 抹平：

```javascript
// 打平：所有嵌套回复铺到第二层
for (const c of raw) { const flat = []; function collect(list) {...} if (c.replies) collect(c.replies); c.replies = flat }
```

### 2.14 命名空间 mock：`from x import y` 的引用拷贝（`378ca2c`，反复复发）

```python
# 各路由模块在 import 时已拿到原始函数引用，需在自身命名空间也 mock
import app.routers.admin as admin_mod
admin_mod.delete_user_permissions = AsyncMock()
```

patch `app.services.permission_service.delete_user_permissions` **改不到** `app.routers.admin` 命名空间里那份旧引用。这个坑在本阶段反复出现：
- `6b45704` 又要分别注入 `ranking_service.redis_client` 和 `cache_consistency.redis_client`
- `273c2c6` 的 `like_service` 同理
- `9311e2e` 的测试被迫嵌套两层 `with patch(...)`

> 根因：全局单例 `redis_client` 靠模块级 import 绑定注入，没走 FastAPI 依赖注入或 `app.state`，**patch 点随 import 关系扩散**。

### 2.15 likes 表主键：复合主键 → 重建 → PG 约束冲突（跨 2 个月）

**（a）`3a5e88e` 建表就错**

```python
sa.PrimaryKeyConstraint('id', 'target_type'),          # ← 把业务枚举塞进主键
sa.UniqueConstraint('user_id','target_type','target_id', name='unique_like_per_user_per_target')
```

主键带 `target_type`（`"article"`/`"comment"`）意味着行身份耦合了类型，`WHERE id = ?` 走不了纯主键索引，想加第三种点赞目标就得动主键。

**（b）`710a17c` 重建（SQLite 不支持改主键，只能 recreate）**
迁移 docstring：`SQLite 不支持 ALTER TABLE 修改主键，需要 recreate 表。`
策略：`create likes_new → copy → drop likes → rename`。**但内联写了 `UniqueConstraint(name=...)`，只在 SQLite 上验证过**。

**（c）`dada73a`（09-13，两个月后）在 PG 上炸**

> 在 PostgreSQL 中，由于命名约束是 schema 级对象，当旧的 likes 表仍持有 `unique_like_per_user_per_target` 约束时，`likes_new` 表再建同名约束会报 **DuplicateTable** 错误。

修法：先建**裸表** → 拷贝 → 换名 → 最后 `op.create_unique_constraint(...)`（此时旧表已 drop，命名不再冲突）；`downgrade()` 同样处理。

**（d）附带坑**：`3a5e88e` 还把 `users.nick_name` 改名为 `nickname`，迁移里是 `add_column('nickname')` + `drop_column('nick_name')` **两步（数据丢失，不是 rename）**；各表 `add_column('like_count', nullable=False)` 没有 `server_default`，有存量数据的库上会直接失败。

### 2.16 缓存对账的缩进 bug：`return` 写在 for 里（`9f57f02` 埋，`6b45704` 修）

```python
    for key in keys:
        ...
        logger.warning("文章浏览量对账修复 slug=%s ...", slug, db_views, redis_views)
        return fixed          # ← 缩进在 for 内，第一处不一致就返回
```

后果：`reconcile_article_view_counts` **每轮最多只修 1 条**，`run_cache_consistency_once` 返回的 `fixed_views` 永远是 0/1。
隐蔽性来源：同文件 `reconcile_like_counts` 的缩进是对的，两个函数长得几乎一样——复制粘贴漏改；而测试只造了**一个**不一致文章（`assert fixed == 1`），全绿。

### 2.17 `view_count` 字段拼错 → 后台任务静默死亡（`9311e2e` 埋，`9f57f02` 修）

```python
.order_by(Article.view_count.desc(), Article.like_count.desc())   # 模型里叫 views
```

`Article.view_count` 不存在 → 构造 `select()` 即抛 AttributeError；`_cache_rebuild_loop()` 只捕获 `CancelledError` → **任务静默死亡**，日志里"重建缓存成功"从未出现过。同一提交里 `ranking_service` 用的是正确的 `article.views`——一处对两处错，说明是笔误。

### 2.18 `stop_` 写成了 `start_` 的位置（`9f57f02` 埋，`f21ecdc` 修）

```python
await start_cache_rebuild_task()
await stop_cache_consistency_task()      # ← 应为 start_
```

`stop_*` 在 `_cache_consistency_task` 为 None 时直接 `return`，所以启动时是**无害的 no-op**，但 `start_cache_consistency_task()` 从未被调用（该函数被 import 却从未使用，是 linter 早该报的 unused import）。**整条缓存一致性对账链路从 07-13 到 07-16 从未运行**——这也是 2.16 那个缩进 bug 一直没暴露的另一个原因。

### 2.19 最大的一次坑：redis-py 8.0 `socket_timeout` 雪崩（`8da7481`）

> 修复 redis-py 8.0升级后默认socket_timeout从None变为5s的问题，该问题导致阻塞读语义被破坏，引发 consumer 静默死亡、缓存预热失效，最终导致请求路径降级到 DB 引发雪崩。

链条：`XREADGROUP BLOCK 5000` 撞上客户端 5s socket 超时 → `TimeoutError` 裸抛 → consumer 退出 → 缓存预热失效 → 请求路径降级查 DB → 熔断器打开 → 雪崩。
症状是 **p99 恶化**，定位手段是 **py-spy + 连接参数审计**。
修复三处：

```python
# app/core/redis.py
redis_client = redis.Redis(..., decode_responses=True, socket_timeout=None)

# app/core/like_stream.py
except RedisTimeoutError:
    return []          # 视为空轮询，下轮重试
```

外加 `cache_consistency.py` / `cache_rebuild.py` 统一改用 `app.core.database.create_engine`。
**这个雷是阶段 C 自己埋下并写进报告的**：`like-concurrency-report-v2.md` 结尾写着"Worker 在消费完成后的下一次阻塞读取中触发 Redis TimeoutError 并退出……生产部署前应修复消费者的空闲超时处理"——一个月后以雪崩形态爆发。

### 2.20 Stream 起点 `"$"` vs `"0"`：启动前的事件永久丢失（`ef1a039`）

```diff
-LIKE_GROUP_START_ID = "$"
+LIKE_GROUP_START_ID = "0"
```

`XGROUP CREATE ... $` 表示"从此刻起只读新消息"。压测流程是"压测期间暂停 Worker，再单独启动 Worker 测追平速度"——组创建时事件已在流里，用 `$` 起步把积压全部当历史跳过，**这些事件永远不会进 pending，死信机制也救不回来**。表现为 Redis 有点赞、SQLite `Likes` 和 `like_count` 永远没有。
验证数据：待消费 15767 条，追平耗时 **46.593 秒（≈338.40 条/秒）**，追平后 `lag=0`、`pending=0`。

### 2.21 请求路径同步写库：删了又加、加了又删（`c850b09` 删 → `f21ecdc` 加回 → `ef1a039` 再删）

`f21ecdc` 在 `change_like_status_cached()` 里把 `await _set_like_status_in_db(...)` 加了回去，同级还有 `routers/likes.py` 的同步 `create_notification(db, ...)`（内部 `db.add()` + `commit()` + `refresh()`）。
结果：Redis 侧为了消除双写不一致窗口做到了单 EVAL 原子，**DB 侧却在同一请求里串行做了 3 次 SQLite 写事务 + 1 次 refresh 读**——优化对象（Redis 竞态）和实际瓶颈（SQLite 写锁）不在同一层面。
`ef1a039` 再次删除，理由写在报告里："Redis 成功后请求仍同步写数据库，同时 Stream Worker 再次落库，导致**唯一键冲突和 SQLite 锁竞争**"。

### 2.22 toggle 语义在并发下是错的（`59e26a3`，最大的一次修正）

旧 Lua 是 toggle：**每个请求都翻转状态并 XADD 一条事件**。两个问题：
1. **重复点击/重试产生多余事件**：用户双击、前端重发都产生新事件。15000 个请求产生 **15767 条**待消费事件，Worker `_dedupe` 后绝大部分互相抵消，纯属浪费落库吞吐（338 条/秒的 SQLite 瓶颈被垃圾流量占满）。
2. **状态翻转竞态**：最终状态 = 初始状态 XOR 请求次数。两个并发的"我想点赞"结果是赞了又取消。

改为幂等状态设置（`PUT` + `is_liked` 显式传参）：

```lua
if desired == 1 then changed = redis.call("SADD", KEYS[1], ARGV[1])
else changed = redis.call("SREM", KEYS[1], ARGV[1]) end
local count = redis.call("SCARD", KEYS[1])
if changed == 1 then redis.call("XADD", KEYS[2], ...) end   -- 只有真的变了才写流
return {desired, count, changed}
```

- `SADD`/`SREM` 返回值天然就是"是否变更"，不用先 `SISMEMBER`（少一次往返 + 天然幂等）
- 事件量 **15767 → 8599（−45.5%）**
- 计数从独立 `count` String 改为 **`SCARD` 实时取 Set 成员数**——Set 是唯一真相源，count 这类派生冗余迟早漂移
- `changed` 贯穿三层：schema（`LikeMutationOut.changed`）、路由（通知与 WebSocket 推送都加 `if changed` 门控）、服务层（`bump_article_hot_score` 只在 `changed` 时调用，**修复了"重复点已赞文章反复给热度分注水"**）
- 对账改为以 Set 成员数为权威（扫描锚点从 `like:{type}:*:count` 改为 `:loaded`）
- 顺带修隐形 bug：`get_comment_by_id` 抛 `ValueError` → 会冒成 **500**，改为干净 `HTTPException(404, "评论不存在")`

前端仍保留"切换"交互，但协议层把意图显式化：`likesAPI.setArticle(slug, !liked.value)`——即使本地状态漂移，重发的也是同一目标状态，服务器**收敛而非翻转**。

### 2.23 SQLite 写锁：压测才暴露的结构性瓶颈（`d7111e9`）

`scripts/bench.md` 原文：

> 并发 10 → 25，RPS 从 184 跌到 73，之后稳定在 ~75，延迟随并发线性增长（100 并发时 100/76 ≈ 1.3s，符合 Little's Law）。这不是"没到瓶颈"，而是已经撞墙且墙是争抢型的：吞吐量随并发上升反而下降，是典型的单写者锁争用特征。
> **墙在哪？**……每个请求都走到 `routers/likes.py:62` 的 `create_notification(db, ...)`：同步 INSERT + commit 到 SQLite。再加上 Stream consumer 同时在后台批量写 likes 表抢同一把写锁。***你以为在压 Redis 点赞链路，实际在压 SQLite 的 fsync 和文件锁***。

修法（`d7111e9`）：

```python
def create_engine():
    """sql下启动 wal + busy_timeout,允许读写并发"""
    engine = create_async_engine(settings.DATABASE_URL,
        connect_args={"timeout": 30},   # 等锁,而非直接报错
        pool_size=20, max_overflow=10)
    if settings.DATABASE_URL.startswith("sqlite"):
        @event.listens_for(engine.sync_engine, "connect")
        def _set_wal(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    return engine
```

同提交还发现压测客户端自身的问题：`httpx.AsyncClient` 默认 `max_keepalive_connections=20`，高并发档**客户端侧排队污染延迟**。
最终结论（`bench.md`）：SQLite 即使 WAL 也**不能让多个写事务真正并行**，写事务仍全局串行，所以根因要靠换 PG 拔除。

### 2.24 `DetachedInstanceError`：缓存重建出的 User 是"半个对象"（`e52ced4`）

`_user_from_cache()` 从 Redis 字段重建 `User` 并挂一个只含 `id`/`name` 的 `Role` 桩对象，docstring 自己写明：

> 访问桩对象上未缓存的字段（如 `role_obj.permissions`）会抛 DetachedInstanceError，由调用方（permission_service）回源 db。

即在 permission_service 里要专门 `except DetachedInstanceError` 回源。这是"缓存对象冒充 ORM 对象"的固有代价。

### 2.25 nginx `brust` 拼写错误（`36d9462` 埋，`95d7ba5` 修，存活 2 天）

```nginx
-    location ~ ^/api/v1/(login|register)${
-        limit_req zone=auth_per_ip brust=5 nodelay;
+    location ~ ^/api/v1/(login|register)$ {
+        limit_req zone=auth_per_ip burst=5 nodelay;
```

两个错误：
1. `brust=5` → nginx 报 `invalid parameter "brust=5"`，**整个 nginx 容器起不来**（不只是限流失效）。
2. `){` 之间缺空格：`$` 后紧跟 `{` 会被解析成变量名的一部分，配置解析错误。

后端 `rate_limit.py` 的注释也照抄了拼写错误（`# 登录: brust = 5 refill = 5 token/,on`，最后那个 `,on` 又是 `min` 的笔误）。

### 2.26 WebSocket 的三个坑（`673c713` → `f21ecdc` → `89513e4`）

1. **先建组件不接线**：`673c713` 建了 `ConnectionManager` 并注册全局单例，但**没有任何 HTTP 路由暴露 WS 端点**，前端此时用 30 秒轮询。
2. **单连接踢人**：`f21ecdc` 前 `active_connections: Dict[int, WebSocket]`，第二个标签页打开会把第一个踢下线。改为 `dict[int, set[WebSocket]]`，`disconnect(user_id, websocket)` 按具体连接 discard，`is_online` 从 `user_id in ...` 改为 `bool(...get(user_id))`（防空集合误判在线）。
3. **CSWSH 防护**：原来只有 `if origin not in _ALLOWED_ORIGINS: close(4003)`——生产域名不在白名单就误杀正常用户。改为白名单 **或** 同源兜底：`same_origin = urlparse(origin).netloc == websocket.headers.get("host")`。
4. **token 走 query string**：WS 无法自定义 header，只能在 URL 里带 `?token=...`，意味着 **JWT 会进 nginx access log**。
5. **`receive_text()` 只捕获 `WebSocketDisconnect`**：连接被重置时不会走 `disconnect`，`active_connections` 残留死连接（靠 `send_personal_message` 的 except 懒清理兜底）。
6. **token 过期检查只能在前端做**：`89513e4` 在 `useNotifications.js` 里手工 base64url 解码 JWT payload 看 `exp`（不验签），**解析失败一律按过期处理**（宁可误踢也不放坏 token 去打 WS），过期后 `window.location.href = '/login'` 硬跳转。

### 2.27 refresh token 可以当 access token 用

`f6882cb` 引入 refresh token：access/refresh **共用同一 `SECRET_KEY`、同一 HS256**，靠 payload 里 `purpose: "refresh"` 区分。但 `get_current_user` **只读 `payload["sub"]`，不校验 `purpose`** → 一个 7 天有效的 refresh token 可以直接访问所有受保护接口，**access token 30 分钟过期这一设计被完全抵消**。教科书级的"同密钥 + 无受众隔离"问题。

### 2.28 SECRET_KEY 校验的启发式耦合（`f6882cb`）

```python
if self.DATABASE_URL.startswith("postgresql") and self.SECRET_KEY == _DEFAULT_SECRET_KEY:
    raise ValueError("生产环境必须通过环境变量 SECRET_KEY 设置 JWT 密钥，不能使用默认值")
```

**用 `DATABASE_URL` 是否 postgres 来判定"是不是生产环境"**——把环境和数据库驱动耦合了：用 PG 的 CI/开发环境也必须设密钥，而生产若用 SQLite 就完全绕过校验。BREAKING 的实质是：部署时忘记设环境变量，应用在 `Settings()` 实例化期（import 期）就崩。

### 2.29 迁移历史大清洗（`f6882cb` 里藏着的大动作）

这一提交删掉了**全部 6 个历史迁移**（`e2cbb78104a5_init`、`6d4aaee87ad3_add_user_role`、`06d06d07edf7_add_categories_and_tags`、`9c8e2b1f4a5d_add_article_views`、`341886290989_add_article_and_relationships`、`62624e0a83eb_add_rbac_tables`），新建 `2102487aff82_fresh_start.py`（`down_revision = None`，173 行一次性建 12 张表）；`env.py` 从逐个 import 模型改为 `import app.models  # noqa: F401 — registers all tables`；`main.py` 的 lifespan 删掉 `Base.metadata.create_all`，改由 Alembic 管建表。
这解释了为什么 RBAC 的迁移 `62624e0a83eb` 只有 `add_column('users', role_id, nullable=True)` + `create_foreign_key(None, ...)`——**连数据回填都没有**（模型声明却是 `nullable=False`），所以标 BREAKING；也解释了为什么紧接着 `2780959` 要加 destructive 防护。

### 2.30 RBAC 迁移的三处偷懒

1. `role` 字符串 → `role_id` FK：兼容靠 `@property def role(self) -> str: return self.role_obj.name if self.role_obj else "user"` + `relationship("Role", lazy="joined")`。写法聪明，但**旧 `role` 字符串列没 drop**（直到 fresh_start 才消失），过渡期双写。
2. **`role_id == 1` 硬编码**：`routers/admin.py` 里 `if user.role_id == 1: raise HTTPException(400, "不可修改管理员的角色")`——写死的 admin 角色主键，依赖 seed 顺序（DEFAULT_ROLES 里 admin 先入库）。角色表重建就静默失效。
3. **`change_user_permissions(user_id, permissions)` 名不副实**：实现是"查 user 是否存在，然后删缓存"，`permissions` 参数**从未被使用**；连同 `delete_user_permissions` / `cache_user_permissions` / `get_cached_permissions` 四个公共 API 都只是对同一个 key 的单行操作。

### 2.31 云部署适配期的连环小坑（09-17 当天）

1. `07edfc0`：`import os` 重复导入（同文件顶部已 import）→ `0e2b50d` 清理。
2. `07edfc0`：`logging.basicConfig(level=logging.INFO, ...)` 后又 `logging.getLogger().setLevel(settings.LOG_LEVEL)`——两处设级别，读起来要停下来想一下哪个生效。
3. `7c0757a`：`not A or not B` 应为 `not A and not B`（见 2.5）。
4. `d79d931`：Dockerfile 从 exec 形式改成 shell 形式才用得上 `${PORT:-8848}`：`CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8848}"]`。
5. `d79d931`：`alembic/env.py` 从同步引擎改成 `async_engine_from_config`，同步 URL 的 `sync_db_url` 替换逻辑删掉。
6. `a50bbdd` → `cf653e3`：`UPSTASH_REDIS_REST_URL` 引入 11 分钟后改名 `REDIS_URL`（这次改名是对的，"Upstash REST URL" 这个名字与实际用法——`redis.from_url()` 走的是 **RESP 协议不是 REST**——从根上就矛盾）。
7. **Upstash 分支丢了一个已验证的修复**：`redis.from_url(...)` 那条分支**没有传 `socket_timeout=None`**，只有 else 分支（本地 Redis）有——`8da7481` 修好的雪崩问题在云环境的代码路径上原样保留了。

### 2.32 仓库卫生问题（贯穿全程）

- `2a62b3d` 提交过 `app/__pycache__/*.pyc`（`6ccc4cf` 里删除记录 `Bin 1295 -> 0 bytes` 可证）。
- `aebf0dd` 把 `.coverage`（122880 字节二进制）当普通文件提交，`d44fa59` 又更新了一遍（98304 字节）——**CI 工件当源码管**。
- `.vscode/settings.json` 反复变更（`0be9a2d` 加、`c7eaad0` 删）——IDE 配置本不该进版本管理。
- `scripts/create_admin.py` 里 **明文密码** `password = "133466"`（后改 `admin123`）白纸黑字进仓库。
- `.gitignore` 里残留人机对话原文：`# 日志文件（虽然你说不用管，但为了防止误提交，我还是加上，你如果确定不需要可以删掉）`；`app/main.py` 里留 `# bug-3 注入类型不对, 需要用text()包装` 这类现场标注。
- 拼写错误长期存活：`_loacl_rate_limit`（loacl）、`defalutdict`、`retirn_value`/`deleta`（测试里的 Mock 属性名写错，**不报错也不生效**，只是恰好与默认 AsyncMock 行为相同才让测试变绿）、`LikeCacheWarmupError(f"攒点缓存预热失败...")`（攒点应为点赞）。
- 未提交的 `.gitignore` 改动：末尾加 `docs/`（且无换行 `\ No newline at end of file`）。

### 2.33 提交信息本身的问题

- `07edfc0`、`36d9462`、`0e2b50d` 的 commit message **被 ``` 代码块包裹**（写在了 Markdown 代码围栏里）。
- `89513e4`（"将博客系统重构为内容论坛并增强功能"）的 message 列了 6 大功能，**没有一个是本提交实现的**——主题发布、评论互动、点赞、通知系统在更早的提交里就有了；`/topics/new` 等前端改名实际在 `ddcb0c1`。它实际改的是 README 叙事、`asyncio.gather`、压测脚本、WS token 检查、create_admin 幂等化。
- `e1226b6`、`a2bfb44`、`d44fa59` 等大量"一提交多件事"（`e1226b6` 一个提交里塞了：邮箱可选、admin 依赖、异常修复、N+1 优化、admin→backend 改名、取消发布、UI 调整、版本号）。

### 2.34 遗留未修的代码问题（现状）

- `app/core/config.py` 默认值 `DATABASE_URL = "postgresql+asyncpg:///./holocron.db"`——**用 PG 异步驱动指向一个文件名**，语义不通（会尝试连本地 socket 上名为 `./holocron.db` 的库）。
- `APP_NAME = "Holocron Blog"`、`APP_DESCRIPTION = "This is my blog (config)"` 在论坛化后仍是旧文案；`main.py` 根路由 `return {"message": "This is my blog"}`，且 `test/test_main.py` 把这个字符串**断言写死**——改名因测试耦合被延缓。
- 三套名字并存：`Holocron Blog`（config/README 标题）、`Holocron 论坛`（前端导航）、`Holocron Archive`（`frontend/index.html` 的 `<title>`）；后端仍是 `/articles/{slug}`、模型仍叫 `Article`，前端路由叫 `topic-new`。
- `TIMEZONE` / `tz` 死配置（见 2.1）。
- `Article` 软删除 + `is_published` 三态没有明确状态机；`parent_id ondelete="SET NULL"` 与"父评论已删仍放行回复"是两套语义叠加。
- `app/api/v1/endpoints/`（auth、users）与 `app/routers/` 双轨目录并存，`/api/v2` 从未出现。
- `per_page: int = Query(20, le=50)` **没有 ge**（`page` 有 `ge=1`），传负数时 offset 计算为负。
- `LikeHistoryOut` 同时有 `title`/`article_title`、`url`/`article_url` 五组重复字段（`enrich_like_history_items` 里手工赋同样的值），后端为前端布局定型——60 行命令式拼装代码。

---

## 3. 反思

### 3.1 复杂度增长 vs 底层承载力（最本质的一对矛盾）

07-02 → 07-14 十天内新增的基础设施：

| 引入提交 | 新增组件 |
|---|---|
| `273c2c6` | like_service 的 Lua、`_like_keys` 键空间、预热锁 |
| `fd0688e` | `app/core/like_stream.py`（消费者 + 生命周期） |
| `c850b09` | 熔断器、死信队列、`_persist_latest_states`、独立消费者进程、滑动窗口限流 |
| `36d9462` | 令牌桶 Lua、Pub/Sub 预热监听器、nginx 双层限流 |
| `9311e2e` | `article_cache_service`、`cache_rebuild` 循环 |
| `9f57f02` | `cache_consistency` 循环、`ranking_service` ZSet |

`main.py` 的 lifespan 膨胀到 **5 个 start + 5 个 stop**，每个都是手写 `_task: asyncio.Task | None` + `global` + `if _task and not _task.done(): return` + `cancel() + try/except CancelledError` 的**复制粘贴模板**（四套）。任何新增后台任务都要重复这 15 行——2.18 那个 start/stop 写错正是这个模板的直接产物（四个模板长得一样，返回 `None`，调 `stop_` 完全合法，类型检查抓不到）。

而这一切跑在 **SQLite（默认无 WAL）** 上，Stream 消费者默认与 API 同进程（`LIKE_STREAM_IN_PROCESS: bool = True`），"workload isolation" 默认关闭。**优化对象和实际瓶颈不在同一层面**——这是整个阶段 B 最值得记的一条。

### 3.2 过度设计的痕迹

- **限流三层同时存在**：滑动窗口 ZSet + penalty box、令牌桶，**再叠** nginx `limit_req_zone`。三个机制对同一批流量独立计数，参数无推导关系（`_DEFAULT_LIMIT=60/min` vs 令牌桶 `20 burst + 1/s` vs nginx `10r/s + burst=30`）。任何调参要改三处，429 响应体还完全相同（先要判断是哪一层拦的）。
- **两份路径配置表**：`_get_path_limit()` 与 `_get_token_bucket()` 对同样的 `/api/v1/login`、`/api/v1/register` 各维护一份（`(3, 3/60)` 与 `5`、`(5, 5/60)` 与 `5`），同一信息两种表示，容易漂移。
- **手写 Redis fake**：`FakeLikeRedis` 到 `6b45704` 已 120+ 行（strings/sets/streams/zsets 四个 dict + 20 多个方法）。它实现了 zset 操作，但**没有实现 `eval`**——本阶段最核心的三段 Lua（点赞原子切换、滑动窗口、令牌桶）在测试里全是 `m.eval = AsyncMock(return_value=[0, 2])` 跳过；`publish`/`pubsub` 的 fake 是 `if False: yield None`（空转）。而且 `scan` 只扫 `strings` 不扫 `sets`，与真实实现返回的 key 集合不同——**手写 fake 的建模偏差会静默影响覆盖范围**。
- **两个功能重叠的压测脚本**：`benchwork_cache_governance.py` 与 `benchwork_likes.py` 都是 concurrency × requests 打 URL 统计分位，各写一套 `percentile()`/`worker()`/`main()`，无共享代码。
- **缓存一致性做对账，但 Stream 承载了全量点击流量**（`MAXLEN 200000`，在 75 RPS 下约 45 分钟被截断）；对一个"状态切换"语义的事件流，理论上可以完全不传事件、由对账反向同步。

### 3.3 正面的过度设计：Pub/Sub 预热（值得单独记）

`c850b09` 的注释里诚实标注了自旋方案的缺点并给出升级路径：

```
TODO 缓存预热
可以升级为redis分布式锁 + 双重锁检查: 自旋退出之前再做一次existing检查
还可以不做自旋,自旋会在asyncio里阻塞事件循环,虽然有sleep让出,但是盲等可优化
故引入**本地缓存 + Redis Pub/Sub缓存失效广播**:对于每个worker维护一个asyncio.Event
预热完成之后publish 事件like:warmed:{target_id} 其他的worker通过Pub/Sub广播唤醒,无需自旋轮询
```

`36d9462` 兑现了它：`_warm_events: dict[str, asyncio.Event]` + `psubscribe` 通配监听 + `asyncio.wait_for(event.wait(), timeout=...)` 兜底 + `finally` 里 `punsubscribe`/`close`（带 `suppress`）+ 监听器幂等启停。**从一个诚实标注局限的 TODO 到完整实现，这是全程最干净的一次架构演进。**

### 3.4 正确性是"压测驱动"发现的，不是 review 发现的

`$`→`0`、请求路径重复双写、toggle 竞态、SQLite 写锁、redis-py 超时——**这五个问题全不是 code review 发现的**，路径都是"写压测 → 数字不对 → 查 → 修 → 复压"。
好处：闭环真实、有数字背书、结论可写进简历。
风险：没被压测覆盖的路径（通知流、评论写路径、权限缓存）同类坑可能还在。

### 3.5 产品转向的半途状态

论坛化只推进到**叙事层**（README、前端标题、`/topics/new` 路由），**数据模型、路由、权限模型一行未动**：后端仍是 `Article/slug/is_published`，权限仍是"作者或 admin"，而论坛需要的是社区治理模型（版块、置顶、跟帖、版主）。权限侧已经露出苗头：`ddcb0c1` 专门给普通用户加 `ARTICLE_CREATE`——原博客模型默认只有 admin 能发文章，转论坛第一件事就是开发帖权，**数据模型没改，权限先打补丁**。
代价：要么后续做破坏性迁移改 `articles` 表语义，要么永远背着"article 其实是 topic"的比喻债。

### 3.6 配置里做业务逻辑

`Settings._normalize_and_check()` 里做 URL 字符串手术（`postgresql://` → `postgresql+asyncpg://`，`95ed934` 时期还有反向转换），后来加了校验器要求"必须 postgresql+asyncpg，否则抛 ValueError"。
问题是：**同一套代码在本地开发和云部署两套期望之间反复横跳**——本地要 SQLite（`4c5bc78` 加转换），后来全面 PG（`bcd1854`/`e09cc4e` 删掉 SQLite 逻辑），现在默认值就写成了 `postgresql+asyncpg:///./holocron.db`（见 2.34）。配置项的默认值应当是可运行的最小值，而不是某个阶段残留的半成品。

### 3.7 测试策略的盲区

- Lua 无覆盖（见 3.2）。
- `test/core/test_exceptions.py` 里留下的现场注释很有价值：`raise_app_exceptions=False: RuntimeError 抛出 → global_exception_handler 应该捕获并返回 JSONResponse *然而!* ASGITransport 在中间拦截了`。
- `test/conftest.py` 的 `# in-memory SQLite 是 per-connection 的，不同 session 互不可见 → 改用临时文件数据库` —— 这是踩过才知道的坑，写进注释是对的。
- 测试耦合延缓改动：`test_main.py` 断言 `"This is my blog"`，导致改名要连带改测试（见 2.34）。

### 3.8 提交习惯

- 巨型提交多（`31a34fe` 31 文件、`e1226b6` 一提交八件事），`git bisect` 会很难用。
- commit message 与 diff 不符（`89513e4` 最典型）。
- 三个 message 被 ``` 包裹。
- 好处是有的：`fcdde7e` 之后**"注释里写 TODO → 下一次实现它"成了习惯**，`c850b09`/`36d9462`/`9f57f02` 里那些说明取舍的长注释都源于此；`bench.md` 报告文化也留下来了。这些是真正的资产。

### 3.9 数据库方言差异：只有真上生产才暴露

`710a17c` 的 likes 主键重建在 SQLite 上完全正常，两个月后在 PG 上因**命名约束是 schema 级对象**报 DuplicateTable（`dada73a`）。
同类：`alembic/env.py` 用同步引擎在本地没问题，部署到云上因为 URL 是 asyncpg 驱动而必须改成异步（`d79d931`）。
教训：**涉及方言的迁移要在目标数据库上验证**，`render_as_batch=True` 从 `2780959` 起就已配置（SQLite recreate 表的官方解法），但 `710a17c` 当时仍选择手写 create/copy/drop/rename。

### 3.10 部署期的"环境变量漂移"

`REDIS_URL` 分支漏传 `socket_timeout=None`（2.31 第 7 条）说明：**同一个客户端的两个初始化分支，只有一条路径被验证过**。`07edfc0`→`7c0757a` 的 `or`/`and` 也说明：**没有被测过的分支（Vercel/Render）写法全靠推演**。
部署适配期最缺的就是"在真实平台上跑一遍"——而这段代码的验证只能靠线上。

---

## 4. 亮点

### 4.1 接口协议：统一 `Response<T>` + 全局异常处理器（`5089d1f`）

`schemas/common.py` 的 `Response(Generic[DataT])`（`code`/`message`/`data`）+ `ErrorResponse` + `exceptions.py` 一次注册三类处理器（HTTPException / RequestValidationError / Exception）。
价值：**接口形状从"每个端点各回各的"变成"一个协议"**，前端可以写一个统一拦截器（`unwrap`）。虽然带来漏网与 204 例外（见 2.7），方向是对的——这是全程最早也最正确的一个架构决策。

### 4.2 删除重复：CRUD 路由工厂（`0be9a2d`）

`create_crud_router(model, create_schema, update_schema, output_schema, prefix, tags, resource_name)` 生成 list/create/update/delete 四端点，categories.py/tags.py 从 89/87 行缩到十几行（该提交 **-178 行**）。
`e1226b6` 又把三处重复的 `if current_user.role != "admin"` 换成 `Depends(get_current_admin_user)`——守卫提到依赖层。

### 4.3 服务层抽取 + 单例 markdown（`d44fa59`）

`routers/articles.py` 一次 **-314 行**，`services/article_service.py` +143 行（`query_articles` / `create_article` / `update_article` / `resolve_slug_conflict` / `set_article_tags`）。
同时把 `mistune.create_markdown()` 从"每请求新建"改成模块级 `_markdown = mistune.create_markdown()` **单例**——这是真实的性能修复。

### 4.4 点赞链路：Lua 原子 + Stream 异步 + 死信 + 熔断（`273c2c6` → `59e26a3`）

- **单 EVAL 原子**：Set 切换 + 计数 + `XADD` 三件事在 Redis 单线程内完成，彻底消除"状态已改但事件丢失"的双写窗口，`count < 0` 有钳位。
- **分布式锁防击穿**：`SET NX EX` + 拿锁后双重检查（避免等待期间别人已预热自己再查一遍 DB）；锁 TTL 5 秒 < 用户可感知超时，进程崩了锁自动释放。
- **Stream 批量落库**：`_persist_latest_states` 一次查询 + 批量 INSERT + 批量 DELETE（`tuple_ ... in_`）+ 单次 commit，把 N 倍 DB 开销压成常数；`_dedupe` 按 key 只留最新一条（点赞是状态不是增量）。
- **死信队列**：`_claim_stale_pending` 读 `times_delivered`，`>= 3` 就 `XRANGE` 取原始 fields → `XADD` 到 `like:events:deadletter`（附 `source_id`/`reason`）→ `XACK`，把 poison message 摘出去。
- **熔断器**：CLOSED → OPEN → HALF_OPEN，`monotonic()` 计时，注释诚实标明"当前阶段: 进程内计数器;多 worker 下每个进程独立计数"。
- **独立消费者进程**：`python -m app.core.like_stream`，自带独立 engine（`finally: await engine.dispose()`），消费者名 `f"{socket.gethostname()}:{id(asyncio.current_task())}"`。
- **幂等化改造**（`59e26a3`）：协议、Lua、DB fallback、Worker、对账**五层全部收敛语义**，事件量 −45.5%，见 2.22。

### 4.5 榜单：排序索引与数据分离（`9f57f02`）

ZSet 只存 `article_id -> score`（浏览权重 1、点赞权重 5），`ZINCRBY` 原子累加；读取时 `ZREVRANGE` 拿 id 再回 DB 取完整数据（`_load_article_by_ids_preserve_order` 显式保序 + 过滤已删/未发布）。
三级降级完整：短 TTL JSON 缓存（`TTL = 60 + random(0,30)` 抖动防雪崩）→ ZSet → DB（并回灌 ZSet）。
异常分类细：`except (ValueError, TypeError, ValidationError, json.JSONDecodeError)` 删坏缓存，`except Exception` 记日志降级；`bump_article_hot_score` 全 fail-open。

### 4.6 Cache-Aside 三件套写全（`9311e2e`）

- **穿透**：`ARTICLE_CACHE_NULL = "__NULL__"` 空值缓存，TTL 只有 30 秒。
- **击穿**：`SET NX EX` 互斥重建（锁 5 秒）+ 双重检查 + 等待循环（50ms × 最多 1 秒），超时**不报错直接回 DB**（注释 `# NOTE await 后直接查询db,若缓存击穿明显,则再加入psub唤醒` 诚实标注了临时性）。
- **雪崩**：`TTL + random.randint(0, JITTER)` 打散过期。
- **脏数据**：`ArticleOut.model_validate_json` 抛 `ValidationError` 时删缓存当 miss（防旧 schema 把接口打成 500）。
- **失效双写**：`update_article` 里缓存 `old_slug` 并失效**新旧两个 slug**（改标题导致 slug 变化时旧缓存不能留）。
- **持久化兜底**：Redis AOF（`--appendonly yes --appendfsync everysec`）+ 每 10 分钟 `rebuild_hot_article_caches()`（取前 100 篇重建）——docstring 说清了"**AOF 只解决进程重启，不解决缓存被淘汰/手动清空**"。

### 4.7 Alembic destructive 防护（`2780959`）

```python
def reject_destructive_autogenerate(context, revision, directives) -> None:
    """阻止 autogenerate 误生成会丢数据的删表/删列迁移。"""
    ...
    if destructive:
        raise RuntimeError("Alembic autogenerate produced destructive operations: " + ", ".join(destructive)
                           + ". Write this migration by hand after backing up the database.")
```

offline/online 两条路径都挂上，配合 `render_as_batch=True`。**在个人项目里很少见的一道防线**，而且它在 `f6882cb` 的迁移大清洗之后立刻发挥了作用。

### 4.8 `ondelete` 策略显式化（`f6882cb` 的 fresh_start）

```
Article.author_id        → users.id       RESTRICT
Article.category_id      → categories.id  SET NULL
Comment.article_id       → articles.id    CASCADE
Comment.author_id        → users.id       RESTRICT
Notification.recipient_id→ users.id       CASCADE
Notification.initiator_id→ users.id       RESTRICT
Notification.article_id  → articles.id    SET NULL
Notification.comment_id  → comments.id    SET NULL
User.role_id             → roles.id       RESTRICT
```

"内容作者不可删、通知接收者删了通知就删、评论删了通知留着但指针置空"——语义清晰自洽。

### 4.9 压测驱动开发 + 报告文化（全程最有价值的方法论）

- `scripts/bench.md`（843 行）记录了**八轮**迭代：原始 wrk 报告 → 换 wrk → WAL → PG 迁移 → 通知异步化，每轮都有完整复现命令、数字表格、"解析"段落。
- `benchwork_cache_governance.py` 的工程化程度：多档位 `--concurrencies "10,25,50,100,200"` + 每档 3 轮取中位数、`discover_article_path()` 自动发现测试目标、`distribute_requests()` 用 `divmod` 精确摊派（替代会丢请求的 `max(1, requests // concurrency)`）、`percentile()` 改 nearest-rank、每档 `warmup_connections` 预热（失败直接 SystemExit）、`httpx.Limits(max_connections=max(concurrencies))`、`trust_env=False` 隔绝代理。
- **压测脚本自己也有测试**：`test/scripts/test_benchwork_cache_governance.py` 用 `httpx.MockTransport` 抛 `RemoteProtocolError` 验证错误统计——业余项目里罕见。
- **可复现的开关**：`RATE_LIMIT_ENABLED`（入口第一行短路，且有 `test_disabled_skips_redis` 断言"关闭时不碰 Redis"，防止"算了限流开销还以为是关了"的假数据）、`BACKGROUND_TASKS_ENABLED`、`LOG_LEVEL`。
- **CI 化**：`--min-peak-rps` / `--max-p95-ms` 超阈值非零退出；成功率非 100% 直接失败并提示"请确认已关闭本地限流"。

### 4.10 其他值得一提的小亮点

- `log_call` 装饰器（`31a34fe`）：一行记录"函数名 + 文件 + 行号"，实现极轻，没有造日志框架。
- `slugify` 保留中文 + `or 'untitled'` 兜底（`31a34fe`）。
- 邮箱可选 + 占位邮箱（`e1226b6`）：`email = user_data.email or f"{user_data.username}@holocron.com"`，对个人博客是合理的减法，且 BREAKING 写进了 message。
- 前台 404 而非 403 掩藏草稿存在性（`e1226b6`）——"不泄露资源存在性"的常规防御。
- 文章作者可删自己文章下的评论（`d44fa59`）——补上了"版主式"治理的真实场景。
- `create_admin.py` 从"先删后建"改为**原地重置**（`89513e4`）：只改 `role_id`/`password`/`is_active` 三个字段，避免删 admin 级联删内容；并从"脚本自建 `CryptContext`（变量名还拼错成 `pwd_content`）"改为复用 `app.core.security.get_password_hash`，消除了哈希算法漂移隐患。
- `asyncio.gather` 并发浏览计数与热度更新（`89513e4`），并消掉一次多余往返（`incr` 的返回值就是新值，旧代码还多 `get` 一次）。**暗坑也记一笔**：`gather` 默认 `return_exceptions=False`，incr 抛错会取消热榜更新，两者语义都 best-effort 所以无害。
- `like_service` 的缓存命中统计 `_cache_stats`（`ca49ed9`）。
- 测试留现场的注释习惯（`c7eaad0` 的 "in-memory SQLite 是 per-connection 的"、`test_exceptions.py` 的 "ASGITransport 在中间拦截了"）。
- CI + 临时文件 SQLite + `dependency_overrides` 从第 4 天就齐了。
- 6 天内交付一个带 RBAC + 测试 + Docker + 前端的系统，这个节奏本身值得记一笔。

---

## 5. 性能演进数据总表

### 5.1 各阶段关键结论

| 阶段 | 状态 | 关键数字 |
|---|---|---|
| 原始（SQLite 非 WAL） | 未修 | 并发 10→25：RPS 从 184 跌到 73，之后稳定 ~75；100 并发延迟 ≈1.3s（Little's Law 吻合）；**吞吐随并发上升反而下降 = 单写者锁争用** |
| 定位 | 报告 | "你以为在压 Redis 点赞链路，实际在压 SQLite 的 fsync 和文件锁" |
| SQLite WAL + 移除请求路径写库 | 修后 | 点赞链路 **826.85 RPS / p99 1.47s**；toggle **861.23 / 1.54s**；100 并发 753.88 / 1.58s；200 并发 781.23 / 1.65s（CPU 到顶 ≈800 RPS，p50 仍 15ms） |
| 迁移 PostgreSQL（`bcd1854`） | 修后 | 见下表 |
| 通知流异步化（`0e36165`） | 修后 | 见下表 |

**SQLite → PG 对比**

| 测试 | SQLite RPS | SQLite p99 | PG RPS | PG p99 | 变化 |
|---:|---:|---:|---:|---:|---|
| 纯框架 | 5754.74 | 36.96 ms | 14088.63 | 9.56 ms | RPS ×2.45 · p99 −74% |
| 一次 SQL | 1033.96 | 135.71 ms | 2976.68 | 65.91 ms | RPS ×2.88 · p99 −51% |
| 点赞链路 | 826.85 | 1470 ms | 1087.04 | 141.45 ms | RPS ×1.31 · **p99 −90%** |
| toggle | 861.23 | 1540 ms | 1153.84 | 129.48 ms | RPS ×1.34 · **p99 −92%** |
| 100 并发 | 753.88 | 1580 ms | 1037.83 | 282.46 ms | RPS ×1.38 · p99 −82% |
| 200 并发 | 781.23 | 1650 ms | 1009.97 | 691.40 ms | RPS ×1.29 · p99 −58% |

**同步通知 → 异步通知（`0e36165`）**

| 测试 | 同步通知 RPS | p99 | 异步通知 RPS | p99 | 变化 |
|---:|---:|---:|---:|---:|---|
| 点赞链路 | 1087.04 | 141.45 ms | 1882.77 | 85.23 ms | RPS ×1.73 · p99 −40% |
| toggle | 1153.84 | 129.48 ms | 1924.31 | 55.90 ms | RPS ×1.67 · p99 −57% |
| 100 并发 | 1037.83 | 282.46 ms | 1553.08 | 156.39 ms | RPS ×1.50 · p99 −45% |
| 200 并发 | 1009.97 | 691.40 ms | 1423.18 | 620.52 ms | RPS ×1.41 · p99 −10% |

**`auto_bench.sh` 5 轮平均（最终态）**

| METRIC | median | min | max |
|---|---:|---:|---:|
| RPS（toggle） | 1738.36 | 1374.51 | 2169.22 |
| p50 ms | 26.82 | 19.46 | 30.61 |
| p99 ms | 59.70 | 53.06 | 141.14 |
| RPS（fixed） | 1997.95 | 1792.23 | 2141.95 |
| p50 ms | 23.89 | 21.58 | 26.60 |
| p99 ms | 55.30 | 41.38 | 59.51 |

### 5.2 单个请求的最终形态（`bench.md` 原文）

> 一次 `PUT /articles/{slug}/like` 包含链路：JWT 认证 → `get_article_like_target`（Redis GET，miss 才查 PostgreSQL）→ …

最终结论（`bench.md`）：

> **请求路径已无任何同步 DB 写入**：认证 + 4 次 Redis 往返 + Lua EVAL + 一次通知 XADD。

RPS 从最初的 **~75** 到最终 **~1900**（约 25 倍），p99 从 **1.5s+** 降到 **~55ms**。

---

## 6. 一页教训清单（回忆用）

1. **时区只定一次**：存储 UTC、展示时区。三轮横跳的代价是 20+ 文件的改动和三天的返工。
2. **统一响应格式要有"收尾清单"**：约定发布后逐端点 grep 检查，别指望记得。
3. **约束放在 DB 还是调用侧要想清楚**：草稿泄露、slug 冲突、唯一约束都是这一类。
4. **`return` / 缩进的 bug 要靠断言兜底**：对账函数只造一条不一致数据的测试等于没测。
5. **后台任务必须有人检查它活着**：`view_count` 拼错 + `stop_`/`start_` 写错，两个 bug 让任务死了三天没人知道。
6. **第三方库升级要审计默认值变更**：redis-py 8.0 的 `socket_timeout` 把整个链路打崩。
7. **阻塞读/消费者组的启动语义要写清楚**：`XGROUP CREATE` 的 `$` 和 `0` 是两个世界。
8. **toggle 是反模式**：有状态的操作一律幂等语义 + `changed` 门控，别让重复请求制造事件。
9. **手写 fake 会撒谎**：`eval` 不实现 = 核心逻辑零覆盖；`scan` 只扫一半 = 覆盖范围静默缩水。
10. **方言差异只有真库能暴露**：改主键、命名约束、异步驱动，都要在目标库上跑一遍。
11. **client 的两个初始化分支要同样对待**：`REDIS_URL` 分支漏了一个已验证的参数。
12. **模板复制粘贴是 bug 温床**：四套 start/stop 的 boilerplate 直接产出一次静默失效，该抽成一个 helper。
13. **压测驱动是最有效的正确性手段**（前提是把报告和脚本一起留在仓库里）。
14. **诚实标注的注释是资产**：`# NOTE ... 若缓存击穿明显,则再加入psub唤醒`、`当前阶段: 进程内计数器;多 worker 下每个进程独立计数`——它们让下一次改动知道边界在哪。
15. **commit message 只写 diff 实际做的事**，否则历史复盘和 bisect 都会被污染。
16. **依赖分层**：requirements-dev / lock，别在 8 分钟里先删后加。
17. **仓库不放二进制、密钥、`.coverage`、IDE 配置**。
