from pathlib import Path

from scripts.benchmark import BenchmarkResult, write_reports


def test_benchmark_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    result = BenchmarkResult(
        request_count=10,
        concurrency=2,
        throughput_rps=100.0,
        p50_latency_ms=5.0,
        p95_latency_ms=9.0,
        retrieval_latency_ms=4.0,
        model_latency_ms=0.0,
        failure_rate=0.0,
        rate_limit_block_rate=0.0,
        refused_count=1,
    )

    json_path, markdown_path = write_reports(result, tmp_path)

    assert json_path.exists()
    assert markdown_path.exists()
    assert "throughput_rps" in json_path.read_text(encoding="utf-8")
    assert "p95 latency" in markdown_path.read_text(encoding="utf-8")
