from __future__ import annotations

from statistics import median

from app.agents.schemas import AgentResponse


def answer_contains_score(answer: str, expected_substrings: list[str]) -> float:
    if not expected_substrings:
        return 1.0
    normalized = answer.lower()
    matches = sum(1 for expected in expected_substrings if expected.lower() in normalized)
    return matches / len(expected_substrings)


def citation_precision(response: AgentResponse, expected_doc_ids: list[str]) -> float:
    cited_doc_ids = [citation.document_id for citation in response.citations]
    if not cited_doc_ids:
        return 1.0 if not expected_doc_ids else 0.0
    expected = set(expected_doc_ids)
    true_positive = sum(1 for doc_id in cited_doc_ids if doc_id in expected)
    return true_positive / len(cited_doc_ids)


def citation_recall(response: AgentResponse, expected_doc_ids: list[str]) -> float:
    expected = set(expected_doc_ids)
    if not expected:
        return 1.0
    cited = {citation.document_id for citation in response.citations}
    return len(cited & expected) / len(expected)


def unsupported_claim_rate(response: AgentResponse) -> float:
    claims = response.critic.unsupported_claims
    if not claims:
        return 0.0
    token_count = max(len(response.answer.split()), 1)
    return min(len(claims) / token_count, 1.0)


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if percentile_value == 50:
        return float(median(values))
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * (percentile_value / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
