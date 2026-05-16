import pytest

from app.ingestion.chunker import chunk_text


def test_chunk_text_preserves_tenant_and_document_metadata() -> None:
    chunks = chunk_text(
        text="one two three four five six seven eight nine ten",
        document_id="doc_123",
        tenant_id="tenant_a",
        source_title="Policy",
        source_uri="policy.txt",
        max_chars=20,
        overlap_chars=5,
    )

    assert len(chunks) > 1
    assert chunks[0].document_id == "doc_123"
    assert chunks[0].tenant_id == "tenant_a"
    assert chunks[0].source_title == "Policy"
    assert chunks[0].chunk_id == "doc_123_chunk_0000"


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text(
            text="hello",
            document_id="doc_123",
            tenant_id="tenant_a",
            source_title="Policy",
            source_uri="policy.txt",
            max_chars=10,
            overlap_chars=10,
        )
