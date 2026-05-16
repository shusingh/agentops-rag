from __future__ import annotations

from typing import Any

from opensearchpy import AsyncOpenSearch

from app.config import get_settings
from app.retrieval.hybrid import hit_from_chunk
from app.retrieval.schemas import IndexedChunk, RetrievalHit

DEFAULT_INDEX_NAME = "agentops-rag-chunks"


class OpenSearchIndex:
    def __init__(self, client: AsyncOpenSearch, index_name: str = DEFAULT_INDEX_NAME) -> None:
        self.client = client
        self.index_name = index_name

    async def index_chunk(self, chunk: IndexedChunk) -> None:
        await self.client.index(
            index=self.index_name,
            id=chunk.chunk_id,
            body=chunk.model_dump(),
            refresh=False,
        )

    async def index_chunks(self, chunks: list[IndexedChunk]) -> None:
        for chunk in chunks:
            await self.index_chunk(chunk)

    async def bm25_search(self, *, tenant_id: str, query: str, top_k: int) -> list[RetrievalHit]:
        response = await self.client.search(
            index=self.index_name,
            body={
                "size": top_k,
                "query": {
                    "bool": {
                        "filter": [{"term": {"tenant_id": tenant_id}}],
                        "must": [{"match": {"text": query}}],
                    }
                },
            },
        )
        hits: list[RetrievalHit] = []
        for raw_hit in response["hits"]["hits"]:
            source = raw_hit["_source"]
            chunk = IndexedChunk.model_validate(source)
            hits.append(hit_from_chunk(chunk, bm25_score=float(raw_hit["_score"] or 0.0)))
        return hits

    async def vector_search(
        self, *, tenant_id: str, query_embedding: list[float], top_k: int
    ) -> list[RetrievalHit]:
        response = await self.client.search(
            index=self.index_name,
            body={
                "size": top_k,
                "query": {
                    "script_score": {
                        "query": {"term": {"tenant_id": tenant_id}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                            "params": {"query_vector": query_embedding},
                        },
                    }
                },
            },
        )
        hits: list[RetrievalHit] = []
        for raw_hit in response["hits"]["hits"]:
            source = raw_hit["_source"]
            chunk = IndexedChunk.model_validate(source)
            hits.append(hit_from_chunk(chunk, vector_score=float(raw_hit["_score"] or 0.0)))
        return hits


def create_opensearch_client() -> AsyncOpenSearch:
    settings = get_settings()
    return AsyncOpenSearch(hosts=[settings.opensearch_url])


async def ensure_chunks_index(
    client: AsyncOpenSearch,
    *,
    index_name: str = DEFAULT_INDEX_NAME,
    dimensions: int = 32,
) -> None:
    exists = await client.indices.exists(index=index_name)
    if exists:
        return

    mapping: dict[str, Any] = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "document_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "tenant_id": {"type": "keyword"},
                "source_title": {"type": "text"},
                "source_uri": {"type": "keyword"},
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dimensions,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                    },
                },
            }
        },
    }
    await client.indices.create(index=index_name, body=mapping)
