

set -a
source .env.bench
set +a

exec wrk "$@"
chmod +x scripts/bench_wrk.sh
#先启动 bench.sh: ./scripts/bench.sh
#then 
# ./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like


# ./scripts/bench_wrk.sh -t4 -c50 -d35s --latency -s scripts/bench_like.lua http://127.0.0.1:8858/articles/1111/like

