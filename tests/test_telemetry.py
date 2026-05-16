import re

import pytest

from app.agents.runtime import AgentRuntime
from app.agents.schemas import AgentRequest
from app.retrieval.embeddings import FakeEmbeddingClient
from app.retrieval.hybrid import InMemorySearchIndex
from app.retrieval.schemas import IndexedChunk


@pytest.mark.asyncio
async def test_agent_runtime_returns_trace_id_from_tracing_context() -> None:
    embeddings = FakeEmbeddingClient(dimensions=16)
    text = "The audit logging policy requires administrative actions to be captured."
    vector = (await embeddings.embed_texts([text]))[0]
    runtime = AgentRuntime(
        index=InMemorySearchIndex(
            [
                IndexedChunk(
                    document_id="doc_audit",
                    chunk_id="chunk_audit",
                    tenant_id="tenant_a",
                    source_title="Audit Policy",
                    source_uri="audit.txt",
                    text=text,
                    embedding=vector,
                )
            ]
        ),
        embeddings=embeddings,
    )

    response = await runtime.run(
        AgentRequest(tenant_id="tenant_a", question="What does audit logging require?")
    )

    assert re.fullmatch(r"[0-9a-f]{32}|trace_[0-9a-f]{32}", response.trace_id)
