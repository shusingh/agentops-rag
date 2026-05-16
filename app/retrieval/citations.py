from __future__ import annotations

from app.agents.schemas import Citation
from app.retrieval.schemas import RetrievalHit


def citation_from_hit(hit: RetrievalHit, *, max_quote_chars: int = 240) -> Citation:
    return Citation(
        document_id=hit.document_id,
        chunk_id=hit.chunk_id,
        title=hit.source_title,
        quote=short_quote(hit.text, max_quote_chars=max_quote_chars),
    )


def short_quote(text: str, *, max_quote_chars: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_quote_chars:
        return compact
    return compact[: max_quote_chars - 3].rstrip() + "..."
