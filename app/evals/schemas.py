from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.schemas import AgentResponse


class EvalCase(BaseModel):
    id: str
    tenant_id: str
    question: str
    expected_answer_contains: list[str] = Field(default_factory=list)
    expected_citation_doc_ids: list[str] = Field(default_factory=list)
    should_refuse: bool


class EvalCaseResult(BaseModel):
    id: str
    tenant_id: str
    question: str
    passed: bool
    latency_ms: float
    answer_contains_score: float
    citation_precision: float
    citation_recall: float
    refusal_correct: bool
    unsupported_claim_rate: float
    response: AgentResponse


class EvalReport(BaseModel):
    dataset: str
    case_count: int
    passed_count: int
    answer_contains_score: float
    citation_precision: float
    citation_recall: float
    refusal_accuracy: float
    unsupported_claim_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    results: list[EvalCaseResult]
