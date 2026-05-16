from __future__ import annotations

from app.ingestion.schemas import Chunk


def chunk_text(
    *,
    text: str,
    document_id: str,
    tenant_id: str,
    source_title: str,
    source_uri: str,
    max_chars: int = 900,
    overlap_chars: int = 120,
) -> list[Chunk]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    chunks: list[Chunk] = []
    start = 0
    ordinal = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        chunk_body = normalized[start:end].strip()
        if chunk_body:
            chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_id=f"{document_id}_chunk_{ordinal:04d}",
                    tenant_id=tenant_id,
                    source_title=source_title,
                    source_uri=source_uri,
                    text=chunk_body,
                    ordinal=ordinal,
                )
            )
            ordinal += 1
        if end == len(normalized):
            break
        start = end - overlap_chars

    return chunks
