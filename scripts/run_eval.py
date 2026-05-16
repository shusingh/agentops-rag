from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.agents.runtime import AgentRuntime
from app.agents.schemas import AgentRequest, AgentResponse
from app.evals.runner import run_eval_dataset, write_eval_report
from app.retrieval.embeddings import FakeEmbeddingClient
from app.retrieval.hybrid import InMemorySearchIndex
from app.retrieval.schemas import IndexedChunk


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AgentOps RAG evals.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", default="evals/expected")
    args = parser.parse_args()
    asyncio.run(run(Path(args.dataset), Path(args.output_dir)))


async def run(dataset_path: Path, output_dir: Path) -> None:
    runtime = await build_demo_runtime()

    async def ask(request: AgentRequest) -> AgentResponse:
        return await runtime.run(request)

    report = await run_eval_dataset(dataset_path=dataset_path, ask=ask)
    json_path, markdown_path = write_eval_report(report, output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


async def build_demo_runtime() -> AgentRuntime:
    embeddings = FakeEmbeddingClient(dimensions=32)
    rows = [
        (
            "demo",
            "doc_marketplace_policy",
            "chunk_marketplace_policy",
            "Marketplace Policy",
            "The marketplace policy requires sellers to respond to seller reviews "
            "and customer review disputes within two business days.",
        ),
        (
            "demo",
            "doc_audit_logging_policy",
            "chunk_audit_logging_policy",
            "Audit Logging Policy",
            "The audit logging policy requires administrative actions to be captured "
            "with actor, timestamp, action, and target resource.",
        ),
        (
            "demo",
            "doc_data_retention_policy",
            "chunk_data_retention_policy",
            "Data Retention Policy",
            "The data retention policy requires deletion review before records are "
            "retained beyond the approved retention window.",
        ),
    ]
    vectors = await embeddings.embed_texts([row[4] for row in rows])
    chunks = [
        IndexedChunk(
            tenant_id=tenant_id,
            document_id=document_id,
            chunk_id=chunk_id,
            source_title=title,
            source_uri=f"{document_id}.txt",
            text=text,
            embedding=vectors[index],
        )
        for index, (tenant_id, document_id, chunk_id, title, text) in enumerate(rows)
    ]
    return AgentRuntime(index=InMemorySearchIndex(chunks), embeddings=embeddings)


if __name__ == "__main__":
    main()
