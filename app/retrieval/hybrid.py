from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

from app.retrieval.embeddings import EmbeddingClient, cosine_similarity, tokenize
from app.retrieval.schemas import (
    HybridSearchResult,
    HybridSearchSummary,
    IndexedChunk,
    RetrievalHit,
)
from app.telemetry.tracing import traced_span


class SearchIndex(Protocol):
    async def bm25_search(self, *, tenant_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        ...

    async def vector_search(
        self, *, tenant_id: str, query_embedding: list[float], top_k: int
    ) -> list[RetrievalHit]:
        ...


class InMemorySearchIndex:
    def __init__(self, chunks: list[IndexedChunk] | None = None) -> None:
        self.chunks = chunks or []

    def add_chunks(self, chunks: list[IndexedChunk]) -> None:
        self.chunks.extend(chunks)

    async def bm25_search(self, *, tenant_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        query_terms = tokenize(query)
        query_counts = Counter(query_terms)
        tenant_chunks = [chunk for chunk in self.chunks if chunk.tenant_id == tenant_id]
        doc_count = len(tenant_chunks)
        doc_frequency = Counter[str]()
        for chunk in tenant_chunks:
            doc_frequency.update(set(tokenize(chunk.text)))

        hits: list[RetrievalHit] = []
        for chunk in tenant_chunks:
            terms = tokenize(chunk.text)
            term_counts = Counter(terms)
            score = 0.0
            for term, query_count in query_counts.items():
                if term_counts[term] == 0:
                    continue
                idf = math.log(
                    1
                    + (doc_count - doc_frequency[term] + 0.5)
                    / (doc_frequency[term] + 0.5)
                )
                score += query_count * term_counts[term] * idf
            if score > 0:
                hits.append(hit_from_chunk(chunk, bm25_score=score))

        return sorted(hits, key=lambda hit: hit.bm25_score, reverse=True)[:top_k]

    async def vector_search(
        self, *, tenant_id: str, query_embedding: list[float], top_k: int
    ) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        for chunk in self.chunks:
            if chunk.tenant_id != tenant_id or not chunk.embedding:
                continue
            score = cosine_similarity(query_embedding, chunk.embedding)
            if score > 0:
                hits.append(hit_from_chunk(chunk, vector_score=score))
        return sorted(hits, key=lambda hit: hit.vector_score, reverse=True)[:top_k]


async def hybrid_search(
    *,
    tenant_id: str,
    query: str,
    index: SearchIndex,
    embeddings: EmbeddingClient,
    top_k: int = 5,
    bm25_weight: float = 0.55,
    vector_weight: float = 0.45,
) -> HybridSearchResult:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if bm25_weight < 0 or vector_weight < 0:
        raise ValueError("weights must be non-negative")
    if bm25_weight + vector_weight == 0:
        raise ValueError("at least one weight must be positive")

    query_embedding = (await embeddings.embed_texts([query]))[0]
    with traced_span("retrieval.bm25_search", tenant_id=tenant_id, top_k=top_k):
        bm25_hits = await index.bm25_search(tenant_id=tenant_id, query=query, top_k=top_k)
    with traced_span("retrieval.vector_search", tenant_id=tenant_id, top_k=top_k):
        vector_hits = await index.vector_search(
            tenant_id=tenant_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

    with traced_span(
        "retrieval.score_fusion",
        tenant_id=tenant_id,
        bm25_hits=len(bm25_hits),
        vector_hits=len(vector_hits),
        top_k=top_k,
    ):
        fused_hits = fuse_hits(
            bm25_hits=bm25_hits,
            vector_hits=vector_hits,
            top_k=top_k,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
        )

    return HybridSearchResult(
        hits=fused_hits,
        summary=HybridSearchSummary(
            top_k=top_k,
            bm25_hits=len(bm25_hits),
            vector_hits=len(vector_hits),
        ),
    )


def fuse_hits(
    *,
    bm25_hits: list[RetrievalHit],
    vector_hits: list[RetrievalHit],
    top_k: int,
    bm25_weight: float,
    vector_weight: float,
) -> list[RetrievalHit]:
    normalized_bm25 = normalize_scores({hit.chunk_id: hit.bm25_score for hit in bm25_hits})
    normalized_vector = normalize_scores({hit.chunk_id: hit.vector_score for hit in vector_hits})

    by_chunk_id: dict[str, RetrievalHit] = {}
    for hit in bm25_hits + vector_hits:
        existing = by_chunk_id.get(hit.chunk_id)
        if existing is None:
            by_chunk_id[hit.chunk_id] = hit.model_copy()
        else:
            existing.bm25_score = max(existing.bm25_score, hit.bm25_score)
            existing.vector_score = max(existing.vector_score, hit.vector_score)

    total_weight = bm25_weight + vector_weight
    for chunk_id, hit in by_chunk_id.items():
        hit.fused_score = (
            bm25_weight * normalized_bm25.get(chunk_id, 0.0)
            + vector_weight * normalized_vector.get(chunk_id, 0.0)
        ) / total_weight

    return sorted(by_chunk_id.values(), key=lambda hit: hit.fused_score, reverse=True)[:top_k]


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lowest = min(values)
    highest = max(values)
    if highest == lowest:
        return {key: 1.0 for key in scores}
    return {key: (value - lowest) / (highest - lowest) for key, value in scores.items()}


def hit_from_chunk(
    chunk: IndexedChunk,
    *,
    bm25_score: float = 0.0,
    vector_score: float = 0.0,
) -> RetrievalHit:
    return RetrievalHit(
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        tenant_id=chunk.tenant_id,
        source_title=chunk.source_title,
        source_uri=chunk.source_uri,
        text=chunk.text,
        bm25_score=bm25_score,
        vector_score=vector_score,
    )
