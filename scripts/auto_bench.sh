#!/usr/bin/env bash
#
# 点赞链路 toggle 批量压测（适配 HolocronBlog）
#   1. source .env.bench（PG 数据库、LIKE_STREAM_IN_PROCESS=false、BENCH_PORT、BENCH_USER/PASSWORD）
#   2. 重启 FastAPI（scripts/bench.sh：--workers $BENCH_WORKERS --no-access-log）
#   3. redis-cli FLUSHDB 清空
#   4. 5s warmup（预热 auth / target / like 缓存，结果丢弃）
#   5. MODE=toggle wrk -t4 -c50 -d60s --latency -s bench_like.lua /articles/1111/like
#   6. 解析 RPS / p50 / p99，重复 N 次，输出 median / min / max
#
set -uo pipefail


RUNS="${RUNS:-1}"
THREADS="${THREADS:-4}"
CONNECTIONS="${CONNECTIONS:-300}"
DURATION="${DURATION:-35s}"
WARMUP="${WARMUP:-10s}"
LUA="scripts/bench_like.lua"

# 加载 bench 配置：DATABASE_URL=PG、BENCH_PORT、BENCH_USER/PASSWORD、BENCH_WORKERS…
set -a
source .env.bench
set +a

PORT="${BENCH_PORT:-8858}"
TARGET="http://127.0.0.1:${PORT}/articles/1111/like"
export MODE=toggle   # 强制 toggle，覆盖 .env.bench 里的 MODE

SERVER_PID=""

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# ---------- 统计工具 ----------
median() {
  printf '%s\n' "$@" | sort -n | awk '
    { a[NR] = $1 }
    END {
      if (NR == 0) { print "nan"; exit }
      if (NR % 2) print a[(NR + 1) / 2]
      else        printf "%.6f\n", (a[NR/2] + a[NR/2+1]) / 2
    }'
}
minv() { printf '%s\n' "$@" | sort -n | head -n1; }
maxv() { printf '%s\n' "$@" | sort -n | tail -n1; }

# 把 wrk 的 "11.00ms" / "300us" / "1.2s" 统一转成 ms 数值
to_ms() {
  awk -v v="$1" 'BEGIN{
    if (v == "") { print "nan"; exit }
    if      (v ~ /ms$/) { sub(/ms$/,"",v); printf "%.3f", v + 0 }
    else if (v ~ /us$/) { sub(/us$/,"",v); printf "%.3f", (v + 0) / 1000 }
    else if (v ~ /ns$/) { sub(/ns$/,"",v); printf "%.3f", (v + 0) / 1e6 }
    else if (v ~ /s$/)  { sub(/s$/,"",v);  printf "%.3f", (v + 0) * 1000 }
    else                { sub(/[a-zA-Z]+$/,"",v); printf "%.3f", v + 0 }
  }'
}

# ---------- 重启 FastAPI ----------
restart_server() {
  log "restarting FastAPI (scripts/bench.sh, workers=${BENCH_WORKERS:-4}, port=$PORT)"
  # 停掉旧的 uvicorn（注意：也会杀掉 8848 的开发服务器）
  pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
  sleep 2

  bash scripts/bench.sh &
  SERVER_PID=$!

  # 健康检查：/ 是公开路由，返回 200（项目没有 /health）
  for _ in $(seq 1 60); do
    if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/"; then
      log "FastAPI is up (pid=$SERVER_PID)"
      return 0
    fi
    sleep 1
  done
  log "ERROR: FastAPI 未能在 60s 内启动"
  return 1
}

# ---------- 依赖检查 ----------
command -v wrk       >/dev/null || { echo "缺少 wrk，请先安装"; exit 1; }
command -v redis-cli >/dev/null || { echo "缺少 redis-cli，请先安装"; exit 1; }
command -v curl      >/dev/null || { echo "缺少 curl"; exit 1; }

restart_server || exit 1

rps_list=(); p50_list=(); p99_list=()

for i in $(seq 1 "$RUNS"); do
  log "================ RUN $i/$RUNS ================"

  # 清空 Redis（auth / target / like 缓存 + like:events + like:notification:events 一起清）
  redis-cli FLUSHDB >/dev/null
  if [[ "$i" != "1" ]]; then
    log "sleep 30s"
    sleep 30
  fi
  # 先单连接预热，避免 FLUSHDB 后多 worker 同时击穿点赞缓存
  log "warmup ${WARMUP} (single connection) ..."
  wrk -t1 -c1 -d"$WARMUP" \
    --latency -s "$LUA" "$TARGET" > /dev/null 2>&1

  if [[ "$(redis-cli EXISTS like:article:1:loaded)" != "1" ]]; then
    log "ERROR: 点赞缓存预热失败，停止本轮压测"
    exit 1
  fi

  # 正式压测
  log "wrk MODE=toggle -t$THREADS -c$CONNECTIONS -d$DURATION $TARGET"
  wrk_output=$(wrk -t"$THREADS" -c"$CONNECTIONS" -d"$DURATION" \
    --latency -s "$LUA" "$TARGET")
  printf '%s\n' "$wrk_output"

  # 解析 RPS / p50 / p99
  rps=$(awk '/^Requests\/sec:/{print $2}' <<< "$wrk_output" | tail -n1)
  p50=$(to_ms "$(awk '/^[[:space:]]+50%/{print $2}' <<< "$wrk_output" | head -n1)")
  p99=$(to_ms "$(awk '/^[[:space:]]+99%/{print $2}' <<< "$wrk_output" | head -n1)")

  if [[ -z "$rps" || "$p50" == "nan" || "$p99" == "nan" ]]; then
    log "WARN: RUN $i 解析失败 (rps='$rps' p50='$p50' p99='$p99')，跳过"
    continue
  fi

  rps_list+=("$rps")
  p50_list+=("$p50")
  p99_list+=("$p99")
  log "RUN $i => RPS=${rps} p50=${p50}ms p99=${p99}ms"
done

# 汇总
if [[ ${#rps_list[@]} -eq 0 ]]; then
  log "没有任何有效结果，退出"
  exit 1
fi

log "=================== SUMMARY ==================="
printf '%-10s %14s %14s %14s\n' METRIC median min max
printf '%-10s %14.2f %14.2f %14.2f\n' \
  RPS "$(median "${rps_list[@]}")" "$(minv "${rps_list[@]}")" "$(maxv "${rps_list[@]}")"
printf '%-10s %14.3f %14.3f %14.3f\n' \
  p50_ms "$(median "${p50_list[@]}")" "$(minv "${p50_list[@]}")" "$(maxv "${p50_list[@]}")"
printf '%-10s %14.3f %14.3f %14.3f\n' \
  p99_ms "$(median "${p99_list[@]}")" "$(minv "${p99_list[@]}")" "$(maxv "${p99_list[@]}")"

log "（FastAPI 仍在后台运行，pid=$SERVER_PID，10s 后kill）"
log "sleep 10s"
sleep 10
kill $SERVER_PID