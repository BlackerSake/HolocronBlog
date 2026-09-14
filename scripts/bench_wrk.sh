#!/usr/bin/env bash
requested_mode="${MODE-}"
set -a
source .env.bench
set +a
if [[ -n "$requested_mode" ]]; then
    export MODE="$requested_mode"
fi

exec wrk "$@"
#先启动 bench.sh: ./scripts/bench.sh
#then 
# MODE=toggle ./scripts/bench_wrk.sh -t4 -c300 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like
