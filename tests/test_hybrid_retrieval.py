import pytest

from app.retrieval.embeddings import FakeEmbeddingClient
from app.retrieval.hybrid import InMemorySearchIndex, fuse_hits, hybrid_search, normalize_scores
from app.retrieval.schemas import IndexedChunk, RetrievalHit


@pytest.mark.asyncio
async def test_hybrid_search_returns_only_tenant_owned_chunks() -> None:
    embeddings = FakeEmbeddingClient(dimensions=16)
    texts = [
        "Audit logging is required for administrative actions.",
        "Audit logging is not visible to this other tenant.",
        "Marketplace sellers must respond to customer reviews.",
    ]
    vectors = await embeddings.embed_texts(texts)
    index = InMemorySearchIndex(
        [
            IndexedChunk(
                document_id="doc_a",
                chunk_id="chunk_a",
                tenant_id="tenant_a",
                source_title="Audit Policy",
                source_uri="audit.txt",
                text=texts[0],
                embedding=vectors[0],
            ),
            IndexedChunk(
                document_id="doc_b",
                chunk_id="chunk_b",
                tenant_id="tenant_b",
                source_title="Other Audit Policy",
                source_uri="other-audit.txt",
                text=texts[1],
                embedding=vectors[1],
            ),
            IndexedChunk(
                document_id="doc_c",
                chunk_id="chunk_c",
                tenant_id="tenant_a",
                source_title="Marketplace Policy",
                source_uri="marketplace.txt",
                text=texts[2],
                embedding=vectors[2],
            ),
        ]
    )

    result = await hybrid_search(
        tenant_id="tenant_a",
        query="What audit logging is required?",
        index=index,
        embeddings=embeddings,
        top_k=5,
    )

    assert result.hits
    assert {hit.tenant_id for hit in result.hits} == {"tenant_a"}
    assert result.hits[0].chunk_id == "chunk_a"
    assert result.summary.bm25_hits >= 1
    assert result.summary.vector_hits >= 1


def test_normalize_scores_handles_empty_singleton_and_range() -> None:
    assert normalize_scores({}) == {}
    assert normalize_scores({"a": 7.0}) == {"a": 1.0}
    assert normalize_scores({"a": 5.0, "b": 10.0}) == {"a": 0.0, "b": 1.0}


def test_fuse_hits_merges_bm25_and_vector_scores_by_chunk_id() -> None:
    bm25_hits = [
        RetrievalHit(
            document_id="doc_1",
            chunk_id="chunk_1",
            tenant_id="tenant_a",
            source_title="Policy",
            source_uri="policy.txt",
            text="alpha",
            bm25_score=10.0,
        ),
        RetrievalHit(
            document_id="doc_2",
            chunk_id="chunk_2",
            tenant_id="tenant_a",
            source_title="Policy",
            source_uri="policy.txt",
            text="beta",
            bm25_score=1.0,
        ),
    ]
    vector_hits = [
        RetrievalHit(
            document_id="doc_2",
            chunk_id="chunk_2",
            tenant_id="tenant_a",
            source_title="Policy",
            source_uri="policy.txt",
            text="beta",
            vector_score=0.9,
        )
    ]

    fused = fuse_hits(
        bm25_hits=bm25_hits,
        vector_hits=vector_hits,
        top_k=5,
        bm25_weight=0.5,
        vector_weight=0.5,
    )

    by_id = {hit.chunk_id: hit for hit in fused}
    assert set(by_id) == {"chunk_1", "chunk_2"}
    assert by_id["chunk_2"].bm25_score == 1.0
    assert by_id["chunk_2"].vector_score == 0.9
    assert all(hit.fused_score >= 0 for hit in fused)
