from pathlib import Path

import pytest

from app.agents.schemas import (
    AgentRequest,
    AgentResponse,
    Citation,
    CriticFinding,
    PlannerAction,
    PlannerDecision,
)
from app.evals.metrics import answer_contains_score, citation_precision, citation_recall
from app.evals.runner import run_eval_dataset, write_eval_report
from app.retrieval.schemas import HybridSearchSummary


def make_response(
    *,
    answer: str,
    citations: list[Citation],
    refused: bool = False,
) -> AgentResponse:
    return AgentResponse(
        answer=answer,
        citations=citations,
        refused=refused,
        trace_id="trace_test",
        retrieval=HybridSearchSummary(
            top_k=5,
            bm25_hits=len(citations),
            vector_hits=len(citations),
        ),
        planner=PlannerDecision(
            action=PlannerAction.RETRIEVE,
            rationale="test",
            rewritten_query="test",
        ),
        critic=CriticFinding(
            supported=not refused,
            should_refuse=refused,
            rationale="test",
        ),
    )


def test_eval_metric_helpers_score_answers_and_citations() -> None:
    response = make_response(
        answer="The policy requires audit logging.",
        citations=[
            Citation(
                document_id="doc_audit",
                chunk_id="chunk_1",
                title="Audit Policy",
                quote="audit logging",
            )
        ],
    )

    assert answer_contains_score(response.answer, ["audit logging"]) == 1.0
    assert citation_precision(response, ["doc_audit"]) == 1.0
    assert citation_recall(response, ["doc_audit", "doc_missing"]) == 0.5


@pytest.mark.asyncio
async def test_run_eval_dataset_scores_cases_and_writes_reports(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        "\n".join(
            [
                '{"id":"case_001","tenant_id":"demo","question":"What is required?",'
                '"expected_answer_contains":["audit logging"],'
                '"expected_citation_doc_ids":["doc_audit"],"should_refuse":false}',
                '{"id":"case_002","tenant_id":"demo","question":"Secret?",'
                '"expected_answer_contains":[],"expected_citation_doc_ids":[],"should_refuse":true}',
            ]
        ),
        encoding="utf-8",
    )

    async def ask(request: AgentRequest) -> AgentResponse:
        if request.question == "Secret?":
            return make_response(answer="", citations=[], refused=True)
        return make_response(
            answer="The policy requires audit logging.",
            citations=[
                Citation(
                    document_id="doc_audit",
                    chunk_id="chunk_1",
                    title="Audit Policy",
                    quote="audit logging",
                )
            ],
        )

    report = await run_eval_dataset(dataset_path=dataset, ask=ask)
    json_path, markdown_path = write_eval_report(report, tmp_path / "expected")

    assert report.case_count == 2
    assert report.passed_count == 2
    assert report.refusal_accuracy == 1.0
    assert json_path.exists()
    assert markdown_path.exists()
    assert "Citation precision" in markdown_path.read_text(encoding="utf-8")
