from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, get_db
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os, logging
from app.api.v1.endpoints import auth
from app.routers import categories, comments, tags
from app.routers import articles
from app.routers import admin
from app.routers import notifications
from app.routers import likes
from app.routers import profile
from app.core.exceptions import register_exception_handlers
from starlette.middleware.base import BaseHTTPMiddleware
from app.middleware.rate_limit import rate_limit_middleware
from app.core.redis import start_sync_task, stop_sync_task
from app.core.seed import seed_default_roles
from app.core.like_stream import start_like_stream_task, stop_like_stream_task
from app.core.notification_stream import start_notification_stream_task, stop_notification_stream_task
from app.services.like_service import start_like_warm_listener, stop_like_warm_listener
from app.core.cache_rebuild import start_cache_rebuild_task, stop_cache_rebuild_task
from app.core.cache_consistency import start_cache_consistency_task, stop_cache_consistency_task
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

import os, sys, logging

handlers = [logging.StreamHandler(sys.stdout)]

# 只在本地（非 Vercel）写文件
if not os.getenv("VERCEL"):
    os.makedirs("logs", exist_ok=True)
    handlers.append(logging.FileHandler("logs/app.log", encoding="utf-8"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
)
logging.getLogger().setLevel(settings.LOG_LEVEL)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期, 由 Alembic 管理建表"""
    await seed_default_roles()
    if settings.BACKGROUND_TASKS_ENABLED:
        await start_sync_task()
        await start_like_warm_listener()
        await start_cache_rebuild_task()
        await start_cache_consistency_task()
        if settings.LIKE_STREAM_IN_PROCESS:
            await start_like_stream_task()
            await start_notification_stream_task()

    yield # 应用运行期间

    if settings.BACKGROUND_TASKS_ENABLED:
        if settings.LIKE_STREAM_IN_PROCESS:
            await stop_like_stream_task()
            await stop_notification_stream_task()
        await stop_sync_task()
        await stop_like_warm_listener()
        await stop_cache_rebuild_task()
        await stop_cache_consistency_task()
    await engine.dispose() # 关闭数据库连接, 相当于@app.on_event("shutdown")

app = FastAPI(
    title = settings.APP_NAME,
    description = settings.APP_DESCRIPTION,
    version = settings.APP_VERSION,
    lifespan=lifespan,
    )
register_exception_handlers(app)
app.include_router(auth.router,
                   prefix="/api/v1",
                   tags=["Authentication"])
app.include_router(categories.router)
app.include_router(tags.router)
app.include_router(articles.router)
app.include_router(comments.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(profile.router)
app.include_router(likes.router)



origins = settings.cors_origin_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 允许的请求源
    allow_credentials=True, # 允许携带cookie
    allow_methods=["*"], # 允许的请求方法, * 表示所有
    allow_headers=["*"], # 允许的请求头, * 表示所有
    max_age=300, # 浏览器缓存CORS响应的最长时间, s
)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

@app.get("/")
async def root():
    """根路由，返回博客欢迎信息"""
    return {"message":"This is my blog"}

@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    """检查数据库连接健康"""
    result = await db.execute(select(1))
    return {"status":"ok",
            "result":result.scalar()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8848, reload=True)
