from __future__ import annotations

from app.agents.schemas import Citation, DraftAnswer
from app.retrieval.embeddings import EmbeddingClient
from app.retrieval.hybrid import SearchIndex, hybrid_search
from app.retrieval.schemas import HybridSearchResult, RetrievalHit


async def retrieve_evidence(
    *,
    tenant_id: str,
    query: str,
    index: SearchIndex,
    embeddings: EmbeddingClient,
    top_k: int = 5,
) -> HybridSearchResult:
    return await hybrid_search(
        tenant_id=tenant_id,
        query=query,
        index=index,
        embeddings=embeddings,
        top_k=top_k,
    )


def draft_answer_from_hits(question: str, hits: list[RetrievalHit]) -> DraftAnswer:
    if not hits:
        return DraftAnswer(text="", citations=[], retrieval_hits=[])

    top_hits = hits[:2]
    citations = [
        Citation(
            document_id=hit.document_id,
            chunk_id=hit.chunk_id,
            title=hit.source_title,
            quote=short_quote(hit.text),
        )
        for hit in top_hits
    ]
    answer = build_grounded_answer(question=question, hits=top_hits)
    return DraftAnswer(text=answer, citations=citations, retrieval_hits=top_hits)


def build_grounded_answer(*, question: str, hits: list[RetrievalHit]) -> str:
    evidence = " ".join(short_quote(hit.text) for hit in hits)
    return f"Based on the retrieved tenant documents: {evidence}"


def short_quote(text: str, max_chars: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
