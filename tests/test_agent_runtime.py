import pytest
from fastapi.testclient import TestClient

from app.agents.runtime import AgentRuntime
from app.agents.schemas import (
    AgentRequest,
    AgentResponse,
    CriticFinding,
    PlannerAction,
    PlannerDecision,
)
from app.api.routes_ask import get_agent_runtime
from app.auth.jwt import create_access_token
from app.config import get_settings
from app.main import app
from app.retrieval.embeddings import FakeEmbeddingClient
from app.retrieval.hybrid import InMemorySearchIndex
from app.retrieval.schemas import HybridSearchSummary, IndexedChunk


@pytest.mark.asyncio
async def test_agent_runtime_answers_with_citations_when_evidence_exists() -> None:
    runtime = await runtime_with_chunks(
        [
            (
                "tenant_a",
                "doc_policy",
                "chunk_policy",
                "Marketplace Policy",
                "The marketplace policy requires sellers to respond to customer reviews.",
            )
        ]
    )

    response = await runtime.run(
        AgentRequest(
            tenant_id="tenant_a",
            question="What does the marketplace policy require for seller reviews?",
        )
    )

    assert response.refused is False
    assert response.citations
    assert response.citations[0].document_id == "doc_policy"
    assert len(response.trace_id) == 32
    assert response.retrieval.bm25_hits >= 1


@pytest.mark.asyncio
async def test_agent_runtime_refuses_when_evidence_is_missing() -> None:
    runtime = await runtime_with_chunks([])

    response = await runtime.run(
        AgentRequest(tenant_id="tenant_a", question="What does the retention policy require?")
    )

    assert response.refused is True
    assert response.citations == []
    assert "not have enough supporting evidence" in response.answer


@pytest.mark.asyncio
async def test_agent_runtime_refuses_sensitive_question_before_retrieval() -> None:
    runtime = await runtime_with_chunks(
        [
            (
                "tenant_a",
                "doc_policy",
                "chunk_policy",
                "Policy",
                "Public policy text.",
            )
        ]
    )

    response = await runtime.run(
        AgentRequest(tenant_id="tenant_a", question="What is the private customer list?")
    )

    assert response.refused is True
    assert response.retrieval.bm25_hits == 0
    assert response.planner.action == "refuse"


def test_ask_endpoint_uses_authenticated_tenant() -> None:
    runtime = RuntimeProbe()
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    client = TestClient(app)
    token = create_access_token(
        subject="user_123",
        tenant_id="tenant_from_token",
        settings=get_settings(),
    )

    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is required?", "tenant_id": "tenant_from_body"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert runtime.seen_tenant_id == "tenant_from_token"


async def runtime_with_chunks(
    rows: list[tuple[str, str, str, str, str]]
) -> AgentRuntime:
    embeddings = FakeEmbeddingClient(dimensions=16)
    texts = [row[4] for row in rows]
    vectors = await embeddings.embed_texts(texts)
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


class RuntimeProbe:
    def __init__(self) -> None:
        self.seen_tenant_id: str | None = None

    async def run(self, request: AgentRequest) -> AgentResponse:
        self.seen_tenant_id = request.tenant_id
        return AgentResponse(
            answer="ok",
            citations=[],
            refused=False,
            trace_id="trace_test",
            retrieval=HybridSearchSummary(top_k=5, bm25_hits=0, vector_hits=0),
            planner=PlannerDecision(
                action=PlannerAction.RETRIEVE,
                rationale="test",
                rewritten_query=request.question,
            ),
            critic=CriticFinding(
                supported=True,
                should_refuse=False,
                rationale="test",
            ),
        )
