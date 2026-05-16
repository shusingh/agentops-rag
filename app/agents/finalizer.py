from __future__ import annotations

from app.agents.schemas import (
    AgentResponse,
    Citation,
    CriticFinding,
    PlannerDecision,
)
from app.retrieval.schemas import HybridSearchSummary


def finalize_response(
    *,
    answer: str,
    citations: list[Citation],
    critic: CriticFinding,
    planner: PlannerDecision,
    trace_id: str,
    retrieval: HybridSearchSummary,
) -> AgentResponse:
    if critic.should_refuse:
        return AgentResponse(
            answer="I do not have enough supporting evidence in this tenant's documents to answer.",
            citations=[],
            refused=True,
            trace_id=trace_id,
            retrieval=retrieval,
            planner=planner,
            critic=critic,
        )

    return AgentResponse(
        answer=answer,
        citations=citations,
        refused=False,
        trace_id=trace_id,
        retrieval=retrieval,
        planner=planner,
        critic=critic,
    )
