#!/usr/bin/env bash
set -a
source .env.bench
set +a

exec uvicorn app.main:app --host 127.0.0.1 \
    --port "$BENCH_PORT" \
    --workers "$BENCH_WORKERS" \
    --no-access-log

# 给uvicorn 用的