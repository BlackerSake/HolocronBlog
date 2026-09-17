FROM python:3.11-slim

WORKDIR /app

# 依赖安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目
COPY . .

# 内部端口 8848
EXPOSE 8848

# 启动命令：先跑迁移，再启动 uvicorn，监听 8848
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8848}"]