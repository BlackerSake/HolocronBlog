from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine, get_db
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import os
from app.api.v1.endpoints import auth
from app.routers import categories, comments, tags
from app.routers import articles
from app.routers import admin
from app.core.exceptions import register_exception_handlers
from starlette.middleware.base import BaseHTTPMiddleware
from app.middleware.rate_limit import rate_limit_middleware
from app.core.redis import start_sync_task, stop_sync_task, redis_client
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "app.log")),
        logging.StreamHandler()
    ]
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期, on_event 方法已经弃用"""
    async with engine.begin() as conn: 
        await conn.run_sync(Base.metadata.create_all)
    await start_sync_task()

    yield # 应用运行期间

    await redis_client.close()
    await stop_sync_task()
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



origins = [
    "http://localhost:8848",
    "https://localhost:8848",
    "http://127.0.0.1:8848",
    "https://127.0.0.1:8848"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 允许的请求源
    allow_credentials=True, # 允许携带cookie
    allow_methods=["*"], # 允许的请求方法, * 表示所有
    allow_headers=["*"], # 允许的请求头, * 表示所有
    max_age=300, # 浏览器缓存CORS响应的最长时间, s
)
app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

@app.get("/")
async def root():
    return {"message":"This is my blog"}

@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)): #Denpends 依赖注入
    """检查数据库连接健康"""
    # 执行一个查询: SELECT 1 用ORM 的select() 方法
    result = await db.execute(select(1))
    # bug-3 注入类型不对, 需要用text()包装,不能执行写裸的sql 
    return {"status":"ok",
            "result":result.scalar()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8848, reload=True)


