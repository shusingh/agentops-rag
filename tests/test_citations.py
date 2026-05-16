from app.retrieval.citations import citation_from_hit
from app.retrieval.schemas import RetrievalHit


def test_citation_from_hit_truncates_long_quotes() -> None:
    hit = RetrievalHit(
        document_id="doc_123",
        chunk_id="chunk_123",
        tenant_id="tenant_a",
        source_title="Policy",
        source_uri="policy.txt",
        text="alpha beta gamma delta",
    )

    citation = citation_from_hit(hit, max_quote_chars=12)

    assert citation.document_id == "doc_123"
    assert citation.chunk_id == "chunk_123"
    assert citation.title == "Policy"
    assert citation.quote == "alpha bet..."
