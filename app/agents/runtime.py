from __future__ import annotations

from uuid import uuid4

from app.agents.critic import critique_answer
from app.agents.finalizer import finalize_response
from app.agents.planner import plan
from app.agents.retriever_agent import draft_answer_from_hits, retrieve_evidence
from app.agents.schemas import AgentRequest, AgentResponse, CriticFinding, PlannerAction
from app.retrieval.embeddings import EmbeddingClient
from app.retrieval.hybrid import SearchIndex
from app.retrieval.schemas import HybridSearchSummary
from app.telemetry.tracing import current_trace_id, traced_span


class AgentRuntime:
    def __init__(self, *, index: SearchIndex, embeddings: EmbeddingClient, top_k: int = 5) -> None:
        self.index = index
        self.embeddings = embeddings
        self.top_k = top_k

    async def run(self, request: AgentRequest) -> AgentResponse:
        with traced_span(
            "agent.runtime",
            tenant_id=request.tenant_id,
            top_k=self.top_k,
            question_length=len(request.question),
        ) as span:
            trace_id = current_trace_id() or f"trace_{uuid4().hex}"
            with traced_span("agent.planner", tenant_id=request.tenant_id):
                decision = plan(request)
            span.set_attribute("planner.action", decision.action.value)
            empty_retrieval = HybridSearchSummary(top_k=self.top_k, bm25_hits=0, vector_hits=0)

            if decision.action in {
                PlannerAction.REFUSE,
                PlannerAction.ASK_CLARIFYING_QUESTION,
            }:
                critic = CriticFinding(
                    supported=False,
                    should_refuse=True,
                    rationale=decision.rationale,
                )
                with traced_span(
                    "agent.finalizer",
                    tenant_id=request.tenant_id,
                    refused=True,
                    citation_count=0,
                ):
                    return finalize_response(
                        answer="",
                        citations=[],
                        critic=critic,
                        planner=decision,
                        trace_id=trace_id,
                        retrieval=empty_retrieval,
                    )

            query = decision.rewritten_query or request.question
            retrieval = await retrieve_evidence(
                tenant_id=request.tenant_id,
                query=query,
                index=self.index,
                embeddings=self.embeddings,
                top_k=self.top_k,
            )
            span.set_attribute("retrieval.bm25_hits", retrieval.summary.bm25_hits)
            span.set_attribute("retrieval.vector_hits", retrieval.summary.vector_hits)
            with traced_span(
                "agent.model_call",
                tenant_id=request.tenant_id,
                model_name="fake-deterministic-drafter",
            ):
                draft = draft_answer_from_hits(request.question, retrieval.hits)
            with traced_span(
                "agent.critic",
                tenant_id=request.tenant_id,
                citation_count=len(draft.citations),
            ):
                critic = critique_answer(
                    answer=draft.text,
                    citations=draft.citations,
                    retrieval_hits=draft.retrieval_hits,
                )
            with traced_span(
                "agent.finalizer",
                tenant_id=request.tenant_id,
                refused=critic.should_refuse,
                citation_count=len(draft.citations),
            ):
                return finalize_response(
                    answer=draft.text,
                    citations=draft.citations,
                    critic=critic,
                    planner=decision,
                    trace_id=trace_id,
                    retrieval=retrieval.summary,
                )
