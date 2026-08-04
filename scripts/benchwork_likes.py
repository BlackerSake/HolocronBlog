import argparse
import asyncio
import statistics
import time
from collections import Counter
from pathlib import Path

import httpx


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


async def run_round(
    client: httpx.AsyncClient,
    path: str,
    requests: int,
    concurrency: int,
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    latencies = []
    statuses = Counter()

    async def send(is_liked: bool) -> None:
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.put(path, json={"is_liked": is_liked})
                statuses[response.status_code] += 1
            except httpx.HTTPError as error:
                statuses[type(error).__name__] += 1
            latencies.append((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    await asyncio.gather(*(send(bool(index % 2)) for index in range(requests)))
    elapsed = time.perf_counter() - started
    return {
        "rps": requests / elapsed,
        "avg_ms": statistics.mean(latencies),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "statuses": statuses,
    }


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    response = await client.post(
        "/api/v1/login",
        data={"username": username, "password": password},
    )
    response.raise_for_status()
    return response.json()["data"]["access_token"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="点赞热 Key 并发压测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8858")
    parser.add_argument("--slug", default="1111")
    parser.add_argument("--username", default="benchuser")
    parser.add_argument("--password", default="Benchpass123")
    parser.add_argument("--concurrencies", default="10,25,50,100,200")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    concurrencies = [int(value) for value in args.concurrencies.split(",")]
    if args.requests <= 0 or args.requests % 2 or args.rounds <= 0:
        parser.error("requests 必须是正偶数，rounds 必须大于 0")

    limits = httpx.Limits(
        max_connections=max(concurrencies),
        max_keepalive_connections=max(concurrencies),
    )
    async with httpx.AsyncClient(
        base_url=args.base_url,
        timeout=30,
        limits=limits,
        trust_env=False,
    ) as client:
        token = await login(client, args.username, args.password)
        client.headers["Authorization"] = f"Bearer {token}"
        path = f"/articles/{args.slug}/like"

        results = []
        for concurrency in concurrencies:
            await run_round(client, path, min(args.requests, concurrency * 2), concurrency)
            rounds = [
                await run_round(client, path, args.requests, concurrency)
                for _ in range(args.rounds)
            ]
            statuses = sum((result["statuses"] for result in rounds), Counter())
            results.append({
                "concurrency": concurrency,
                "rps": statistics.median(result["rps"] for result in rounds),
                "avg_ms": statistics.median(result["avg_ms"] for result in rounds),
                "p95_ms": statistics.median(result["p95_ms"] for result in rounds),
                "p99_ms": statistics.median(result["p99_ms"] for result in rounds),
                "success": statuses[200] / (args.requests * args.rounds) * 100,
                "statuses": dict(statuses),
            })

        status = await client.get(f"/articles/{args.slug}/like-status")
        status.raise_for_status()
        final_status = status.json()

    lines = [
        "# 点赞热 Key 并发压测报告",
        "",
        f"- 目标：`{args.base_url}/articles/{args.slug}/like`",
        f"- 每档：`{args.requests}` 请求 × `{args.rounds}` 轮，取中位数",
        "- 模型：单用户、单文章热 Key，关闭接口限流",
        "",
        "| 并发 | RPS | 平均延迟 ms | p95 ms | p99 ms | 成功率 | 状态码 |",
        "|---:|---:|---:|---:|---:|---:|:---|",
    ]
    for result in results:
        lines.append(
            f"| {result['concurrency']} | {result['rps']:.2f} | "
            f"{result['avg_ms']:.2f} | {result['p95_ms']:.2f} | "
            f"{result['p99_ms']:.2f} | {result['success']:.2f}% | "
            f"`{result['statuses']}` |"
        )
    lines.extend(["", f"- 压测后点赞状态：`{final_status}`"])
    report = "\n".join(lines) + "\n"
    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")

    if any(result["success"] != 100 for result in results):
        raise SystemExit("压测失败：存在非 200 响应")


if __name__ == "__main__":
    asyncio.run(main())
