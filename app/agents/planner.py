from __future__ import annotations

from app.agents.schemas import AgentRequest, PlannerAction, PlannerDecision


def plan(request: AgentRequest) -> PlannerDecision:
    question = request.question.strip()
    if not question:
        return PlannerDecision(
            action=PlannerAction.ASK_CLARIFYING_QUESTION,
            rationale="Question is empty.",
        )

    lowered = question.lower()
    if any(marker in lowered for marker in ["private customer list", "api key", "password"]):
        return PlannerDecision(
            action=PlannerAction.REFUSE,
            rationale="Question asks for sensitive information outside the document corpus.",
        )

    return PlannerDecision(
        action=PlannerAction.RETRIEVE,
        rationale="Question requires tenant-scoped document evidence.",
        rewritten_query=question,
    )
