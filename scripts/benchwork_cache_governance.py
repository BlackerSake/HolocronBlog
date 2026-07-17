import argparse
import asyncio
import math
import statistics
import time
from pathlib import Path

import httpx


def parse_concurrencies(value: str) -> list[int]:
    try:
        levels = [int(item) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("并发档位必须是逗号分隔的整数") from exc
    if not levels or any(level <= 0 for level in levels):
        raise argparse.ArgumentTypeError("并发档位必须大于 0")
    return levels


async def discover_article_path(client: httpx.AsyncClient) -> str:
    """从当前 API 自动选择第一篇公开主题。"""
    response = await client.get("/articles", params={"page": 1, "per_page": 1})
    response.raise_for_status()
    items = response.json().get("data", {}).get("items", [])
    if not items:
        raise SystemExit("当前 API 没有已发布主题，请先发布主题或通过 --path 指定路径")
    return f"/articles/{items[0]['slug']}"


def percentile(values: list[float], percent: float) -> float:
    """使用 nearest-rank 计算分位数。"""
    if not values:
        return 0.0
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * percent) - 1)]


def distribute_requests(total: int, concurrency: int) -> list[int]:
    """将请求精确分配给并发 worker。"""
    base, remainder = divmod(total, concurrency)
    return [base + (index < remainder) for index in range(concurrency) if base or index < remainder]


async def worker(
    client: httpx.AsyncClient,
    path: str,
    requests: int,
    latencies: list[float],
    status_codes: dict[int, int],
    errors: dict[str, int],
) -> None:
    for _ in range(requests):
        started = time.perf_counter()
        try:
            response = await client.get(path)
        except httpx.RequestError as exc:
            name = type(exc).__name__
            errors[name] = errors.get(name, 0) + 1
            continue
        latencies.append((time.perf_counter() - started) * 1000)
        status_codes[response.status_code] = status_codes.get(response.status_code, 0) + 1


async def run_round(
    client: httpx.AsyncClient,
    path: str,
    requests: int,
    concurrency: int,
) -> dict:
    latencies: list[float] = []
    status_codes: dict[int, int] = {}
    errors: dict[str, int] = {}
    started = time.perf_counter()
    cpu_started = time.process_time()
    await asyncio.gather(*[
        worker(client, path, count, latencies, status_codes, errors)
        for count in distribute_requests(requests, concurrency)
    ])
    elapsed = time.perf_counter() - started
    client_cpu_percent = (time.process_time() - cpu_started) / elapsed * 100
    return {
        "吞吐量_rps": status_codes.get(200, 0) / elapsed,
        "平均延迟_ms": statistics.mean(latencies) if latencies else 0.0,
        "p95延迟_ms": percentile(latencies, 0.95),
        "p99延迟_ms": percentile(latencies, 0.99),
        "客户端CPU百分比": client_cpu_percent,
        "状态码": status_codes,
        "传输错误": errors,
    }


async def warmup_connections(
    client: httpx.AsyncClient,
    path: str,
    concurrency: int,
    rounds: int,
) -> None:
    for _ in range(rounds):
        responses = await asyncio.gather(*[
            client.get(path) for _ in range(concurrency)
        ], return_exceptions=True)
        failed = [
            type(response).__name__ if isinstance(response, Exception) else response.status_code
            for response in responses
            if isinstance(response, Exception) or response.status_code != 200
        ]
        if failed:
            raise SystemExit(f"预热失败: {failed[0]} {path}")


def summarize(concurrency: int, rounds: list[dict], requests: int) -> dict:
    status_codes: dict[int, int] = {}
    errors: dict[str, int] = {}
    for result in rounds:
        for code, count in result["状态码"].items():
            status_codes[code] = status_codes.get(code, 0) + count
        for name, count in result["传输错误"].items():
            errors[name] = errors.get(name, 0) + count
    total = requests * len(rounds)
    return {
        "并发数": concurrency,
        "吞吐量_rps": statistics.median(result["吞吐量_rps"] for result in rounds),
        "平均延迟_ms": statistics.median(result["平均延迟_ms"] for result in rounds),
        "p95延迟_ms": statistics.median(result["p95延迟_ms"] for result in rounds),
        "p99延迟_ms": statistics.median(result["p99延迟_ms"] for result in rounds),
        "客户端CPU百分比": statistics.median(result["客户端CPU百分比"] for result in rounds),
        "成功率": status_codes.get(200, 0) / total * 100,
        "状态码": status_codes,
        "传输错误": errors,
    }


def render_report(
    base_url: str,
    path: str,
    requests: int,
    rounds: int,
    warmup: int,
    results: list[dict],
) -> str:
    peak = max(results, key=lambda result: result["吞吐量_rps"])
    lines = [
        "# 缓存并发压测报告",
        "",
        f"- 目标: `{base_url}{path}`",
        f"- 每轮请求数: `{requests}`",
        f"- 每档轮数: `{rounds}`",
        f"- 每档并发预热轮数: `{warmup}`",
        "",
        "| 并发数 | 中位吞吐量 RPS | 平均延迟 ms | p95 ms | p99 ms | 客户端 CPU | 成功率 | 状态码 | 传输错误 |",
        "|---:|---:|---:|---:|---:|---:|---:|:---|:---|",
    ]
    for result in results:
        lines.append(
            f"| {result['并发数']} | {result['吞吐量_rps']:.2f} | "
            f"{result['平均延迟_ms']:.2f} | {result['p95延迟_ms']:.2f} | "
            f"{result['p99延迟_ms']:.2f} | {result['客户端CPU百分比']:.2f}% | "
            f"{result['成功率']:.2f}% | "
            f"`{result['状态码']}` | `{result['传输错误']}` |"
        )
    lines.extend([
        "",
        f"- 峰值并发数: `{peak['并发数']}`",
        f"- 峰值吞吐量_rps: `{peak['吞吐量_rps']:.2f}`",
        f"- 峰值p95延迟_ms: `{peak['p95延迟_ms']:.2f}`",
    ])
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8848")
    parser.add_argument("--path", help="主题详情路径；默认自动选择第一篇公开主题")
    parser.add_argument("--concurrencies", type=parse_concurrencies, default=[10, 25, 50, 100, 200])
    parser.add_argument("--requests", type=int, default=1000, help="每个并发档位每轮请求数")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1, help="每个并发档位的并发预热轮数")
    parser.add_argument("--output", type=Path, help="保存 Markdown 报告")
    parser.add_argument("--min-peak-rps", type=float)
    parser.add_argument("--max-p95-ms", type=float)
    args = parser.parse_args()

    if args.requests <= 0 or args.rounds <= 0 or args.warmup < 0:
        parser.error("requests/rounds 必须大于 0，warmup 不能小于 0")
    if args.requests < max(args.concurrencies):
        parser.error("requests 不能小于最大并发档位")

    limits = httpx.Limits(
        max_connections=max(args.concurrencies),
        max_keepalive_connections=max(args.concurrencies),
        keepalive_expiry=2.0,
    )
    async with httpx.AsyncClient(
        base_url=args.base_url,
        timeout=30,
        limits=limits,
        trust_env=False,
    ) as client:
        path = args.path or await discover_article_path(client)
        results = []
        for concurrency in args.concurrencies:
            await warmup_connections(client, path, concurrency, args.warmup)
            round_results = [
                await run_round(client, path, args.requests, concurrency)
                for _ in range(args.rounds)
            ]
            results.append(summarize(concurrency, round_results, args.requests))

    report = render_report(args.base_url, path, args.requests, args.rounds, args.warmup, results)
    print(report)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")

    peak_rps = max(result["吞吐量_rps"] for result in results)
    if any(result["成功率"] < 100 for result in results):
        raise SystemExit("压测失败: 存在非 200 响应，请确认已关闭本地限流")
    if args.min_peak_rps is not None and peak_rps < args.min_peak_rps:
        raise SystemExit(f"压测失败: 峰值 RPS {peak_rps:.2f} < {args.min_peak_rps:.2f}")
    if args.max_p95_ms is not None and any(
        result["p95延迟_ms"] > args.max_p95_ms for result in results
    ):
        raise SystemExit(f"压测失败: 存在 p95 > {args.max_p95_ms:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
