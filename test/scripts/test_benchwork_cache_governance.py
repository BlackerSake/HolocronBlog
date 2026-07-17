import httpx
import pytest

from scripts.benchwork_cache_governance import (
    distribute_requests,
    render_report,
    run_round,
    summarize,
)


def test_concurrency_summary_and_report():
    counts = distribute_requests(1000, 128)
    assert len(counts) == 128
    assert sum(counts) == 1000
    assert max(counts) - min(counts) <= 1

    result = summarize(128, [{
        "吞吐量_rps": 500.0,
        "平均延迟_ms": 20.0,
        "p95延迟_ms": 30.0,
        "p99延迟_ms": 40.0,
        "客户端CPU百分比": 80.0,
        "状态码": {200: 1000},
        "传输错误": {},
    }], 1000)
    report = render_report("http://test", "/articles/a", 1000, 1, 1, [result])

    assert result["成功率"] == 100
    assert result["客户端CPU百分比"] == 80
    assert "峰值并发数: `128`" in report
    assert "峰值吞吐量_rps: `500.00`" in report


@pytest.mark.asyncio
async def test_transport_error_is_reported():
    async def disconnect(request):
        raise httpx.RemoteProtocolError("server disconnected", request=request)

    async with httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(disconnect),
    ) as client:
        result = await run_round(client, "/", requests=2, concurrency=2)

    assert result["吞吐量_rps"] == 0
    assert result["传输错误"] == {"RemoteProtocolError": 2}
