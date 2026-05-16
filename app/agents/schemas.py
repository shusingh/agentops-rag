from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.retrieval.schemas import HybridSearchSummary, RetrievalHit


class PlannerAction(StrEnum):
    ANSWER_DIRECTLY = "answer_directly"
    RETRIEVE = "retrieve"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    REFUSE = "refuse"


class PlannerDecision(BaseModel):
    action: PlannerAction
    rationale: str
    rewritten_query: str | None = None


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    quote: str


class CriticFinding(BaseModel):
    supported: bool
    missing_citations: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    should_refuse: bool
    rationale: str


class AgentRequest(BaseModel):
    tenant_id: str
    question: str
    conversation_context: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    trace_id: str
    retrieval: HybridSearchSummary
    planner: PlannerDecision
    critic: CriticFinding


class DraftAnswer(BaseModel):
    text: str
    citations: list[Citation]
    retrieval_hits: list[RetrievalHit]
