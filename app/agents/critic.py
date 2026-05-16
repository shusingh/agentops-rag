from __future__ import annotations

from app.agents.schemas import Citation, CriticFinding
from app.retrieval.embeddings import tokenize
from app.retrieval.schemas import RetrievalHit


def critique_answer(
    *,
    answer: str,
    citations: list[Citation],
    retrieval_hits: list[RetrievalHit],
) -> CriticFinding:
    if not retrieval_hits:
        return CriticFinding(
            supported=False,
            should_refuse=True,
            rationale="No retrieved evidence is available.",
            unsupported_claims=[answer] if answer else [],
        )

    if not answer.strip():
        return CriticFinding(
            supported=False,
            should_refuse=True,
            rationale="No answer was drafted from retrieved evidence.",
        )

    cited_chunk_ids = {citation.chunk_id for citation in citations}
    retrieved_chunk_ids = {hit.chunk_id for hit in retrieval_hits}
    missing_citations = sorted(retrieved_chunk_ids - cited_chunk_ids)
    if missing_citations:
        return CriticFinding(
            supported=False,
            missing_citations=missing_citations,
            should_refuse=True,
            rationale="Answer does not cite every retrieved evidence chunk used by the draft.",
        )

    evidence_tokens = set(tokenize(" ".join(hit.text for hit in retrieval_hits)))
    answer_tokens = meaningful_tokens(answer)
    unsupported = sorted(answer_tokens - evidence_tokens)
    unsupported_claims = unsupported[:5]

    if len(answer_tokens) > 0 and len(unsupported) / len(answer_tokens) > 0.65:
        return CriticFinding(
            supported=False,
            unsupported_claims=unsupported_claims,
            should_refuse=True,
            rationale="Most answer tokens are not grounded in retrieved evidence.",
        )

    return CriticFinding(
        supported=True,
        should_refuse=False,
        rationale="Answer is grounded in retrieved chunks and includes citations.",
    )


def meaningful_tokens(text: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "based",
        "be",
        "by",
        "documents",
        "in",
        "is",
        "of",
        "on",
        "or",
        "retrieved",
        "tenant",
        "the",
        "to",
    }
    return {token for token in tokenize(text) if token not in stopwords and len(token) > 2}
