import argparse
import asyncio
import statistics
import time

import httpx


def percentile(values: list[float], percent: float) -> float:
    """计算简单分位数，用于输出 p95/p99 延迟。"""
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, int(len(values) * percent))
    return values[index]


async def worker(
    client: httpx.AsyncClient,
    path: str,
    requests: int,
    latencies: list[float],
    status_codes: dict[int, int],
) -> None:
    """
    单个压测 worker。

    每个 worker 串行发请求，多个 worker 并发运行。
    这样可以模拟高并发下文章详情缓存、热门榜 ZSet、限流与 Redis 计数
    链路的表现。
    """
    for _ in range(requests):
        start = time.perf_counter()
        response = await client.get(path)
        latencies.append((time.perf_counter() - start) * 1000)
        status_codes[response.status_code] = status_codes.get(response.status_code, 0) + 1


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8848")
    parser.add_argument("--path", default="/articles/published-article")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--requests", type=int, default=1000)
    args = parser.parse_args()

    per_worker = max(1, args.requests // args.concurrency)
    latencies: list[float] = []
    status_codes: dict[int, int] = {}

    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=10) as client:
        await asyncio.gather(*[
            worker(client, args.path, per_worker, latencies,
            status_codes)
            for _ in range(args.concurrency)
        ])
    elapsed = time.perf_counter() - started

    total = len(latencies)
    print("# Cache Governance Benchmark")
    print()
    print(f"- target: `{args.base_url}{args.path}`")
    print(f"- total_requests: `{total}`")
    print(f"- concurrency: `{args.concurrency}`")
    print(f"- elapsed_seconds: `{elapsed:.2f}`")
    print(f"- throughput_rps: `{total / elapsed:.2f}`")
    print(f"- avg_latency_ms: `{statistics.mean(latencies):.2f}`")
    print(f"- p95_latency_ms: `{percentile(latencies, 0.95):.2f}`")
    print(f"- p99_latency_ms: `{percentile(latencies, 0.99):.2f}`")
    print(f"- status_codes: `{status_codes}`")


if __name__ == "__main__":
    asyncio.run(main())