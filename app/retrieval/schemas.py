from __future__ import annotations

from pydantic import BaseModel, Field


class IndexedChunk(BaseModel):
    document_id: str
    chunk_id: str
    tenant_id: str
    source_title: str
    source_uri: str
    text: str
    embedding: list[float] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    document_id: str
    chunk_id: str
    tenant_id: str
    source_title: str
    source_uri: str
    text: str
    bm25_score: float = 0.0
    vector_score: float = 0.0
    fused_score: float = 0.0


class HybridSearchSummary(BaseModel):
    top_k: int
    bm25_hits: int
    vector_hits: int


class HybridSearchResult(BaseModel):
    hits: list[RetrievalHit]
    summary: HybridSearchSummary
