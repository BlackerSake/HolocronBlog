from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
app = FastAPI(
    title = settings.APP_NAME,
    description = settings.APP_DESCRIPTION,
    version = settings.APP_VERSION,
    )

origins = [
    "http://localhost.com",
    "https://localhost.com",
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


@app.get("/")
async def root():
    return {"message":"This is my blog"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8848, reload=True)