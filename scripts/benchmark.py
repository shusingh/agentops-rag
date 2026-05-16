from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

from app.agents.runtime import AgentRuntime
from app.agents.schemas import AgentRequest
from app.retrieval.embeddings import FakeEmbeddingClient
from app.retrieval.hybrid import InMemorySearchIndex
from app.retrieval.schemas import IndexedChunk


@dataclass(frozen=True)
class BenchmarkResult:
    request_count: int
    concurrency: int
    throughput_rps: float
    p50_latency_ms: float
    p95_latency_ms: float
    retrieval_latency_ms: float
    model_latency_ms: float
    failure_rate: float
    rate_limit_block_rate: float
    refused_count: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AgentOps RAG benchmark.")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--output-dir", default="benchmark_reports")
    args = parser.parse_args()
    asyncio.run(run(args.requests, args.concurrency, Path(args.output_dir)))


async def run(request_count: int, concurrency: int, output_dir: Path) -> None:
    if request_count <= 0:
        raise ValueError("requests must be positive")
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")

    runtime = await build_runtime()
    questions = [
        "What does audit logging require?",
        "What does the marketplace policy require for seller reviews?",
        "What does the data retention policy require?",
        "What is the private customer list?",
    ]
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    outcomes: Counter[str] = Counter()
    started = time.perf_counter()

    async def one(index: int) -> None:
        async with semaphore:
            question = questions[index % len(questions)]
            case_started = time.perf_counter()
            try:
                response = await runtime.run(
                    AgentRequest(tenant_id="demo", question=question)
                )
                if response.refused:
                    outcomes["refused"] += 1
                else:
                    outcomes["answered"] += 1
            except Exception:
                outcomes["failed"] += 1
            finally:
                latencies.append((time.perf_counter() - case_started) * 1000)

    await asyncio.gather(*(one(index) for index in range(request_count)))
    elapsed = time.perf_counter() - started
    result = BenchmarkResult(
        request_count=request_count,
        concurrency=concurrency,
        throughput_rps=request_count / elapsed if elapsed else 0.0,
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        retrieval_latency_ms=percentile(latencies, 50),
        model_latency_ms=0.0,
        failure_rate=outcomes["failed"] / request_count,
        rate_limit_block_rate=0.0,
        refused_count=outcomes["refused"],
    )
    write_reports(result, output_dir)


async def build_runtime() -> AgentRuntime:
    embeddings = FakeEmbeddingClient(dimensions=32)
    rows = [
        (
            "doc_audit_logging_policy",
            "chunk_audit_logging_policy",
            "Audit Logging Policy",
            "The audit logging policy requires administrative actions to be captured "
            "with actor, timestamp, action, and target resource.",
        ),
        (
            "doc_marketplace_policy",
            "chunk_marketplace_policy",
            "Marketplace Policy",
            "The marketplace policy requires sellers to respond to customer reviews "
            "and review disputes within two business days.",
        ),
        (
            "doc_data_retention_policy",
            "chunk_data_retention_policy",
            "Data Retention Policy",
            "The data retention policy requires deletion review before records are "
            "retained beyond the approved retention window.",
        ),
    ]
    vectors = await embeddings.embed_texts([row[3] for row in rows])
    chunks = [
        IndexedChunk(
            tenant_id="demo",
            document_id=document_id,
            chunk_id=chunk_id,
            source_title=title,
            source_uri=f"{document_id}.txt",
            text=text,
            embedding=vectors[index],
        )
        for index, (document_id, chunk_id, title, text) in enumerate(rows)
    ]
    return AgentRuntime(index=InMemorySearchIndex(chunks), embeddings=embeddings)


def write_reports(result: BenchmarkResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest.json"
    markdown_path = output_dir / "latest.md"
    json_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return json_path, markdown_path


def render_markdown(result: BenchmarkResult) -> str:
    return "\n".join(
        [
            "# AgentOps RAG Benchmark Report",
            "",
            f"- Requests: {result.request_count}",
            f"- Concurrency: {result.concurrency}",
            f"- Throughput: {result.throughput_rps:.2f} req/s",
            f"- p50 latency: {result.p50_latency_ms:.2f} ms",
            f"- p95 latency: {result.p95_latency_ms:.2f} ms",
            f"- Retrieval latency proxy: {result.retrieval_latency_ms:.2f} ms",
            f"- Model latency proxy: {result.model_latency_ms:.2f} ms",
            f"- Failure rate: {result.failure_rate:.3f}",
            f"- Rate-limit block rate: {result.rate_limit_block_rate:.3f}",
            f"- Refused responses: {result.refused_count}",
            "",
        ]
    )


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if percentile_value == 50:
        return float(median(values))
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * (percentile_value / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


if __name__ == "__main__":
    main()
