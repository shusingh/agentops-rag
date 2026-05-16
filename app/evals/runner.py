from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.agents.schemas import AgentRequest, AgentResponse
from app.evals.metrics import (
    answer_contains_score,
    citation_precision,
    citation_recall,
    mean,
    percentile,
    unsupported_claim_rate,
)
from app.evals.schemas import EvalCase, EvalCaseResult, EvalReport

AskFunction = Callable[[AgentRequest], Awaitable[AgentResponse]]


def load_eval_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                cases.append(EvalCase.model_validate_json(stripped))
            except ValueError as exc:
                raise ValueError(f"Invalid eval row at {path}:{line_number}") from exc
    return cases


async def run_eval_dataset(*, dataset_path: Path, ask: AskFunction) -> EvalReport:
    cases = load_eval_cases(dataset_path)
    results: list[EvalCaseResult] = []

    for case in cases:
        request = AgentRequest(tenant_id=case.tenant_id, question=case.question)
        started = time.perf_counter()
        response = await ask(request)
        latency_ms = (time.perf_counter() - started) * 1000

        contains = answer_contains_score(response.answer, case.expected_answer_contains)
        precision = citation_precision(response, case.expected_citation_doc_ids)
        recall = citation_recall(response, case.expected_citation_doc_ids)
        refusal_correct = response.refused == case.should_refuse
        unsupported_rate = unsupported_claim_rate(response)
        passed = (
            contains == 1.0
            and precision == 1.0
            and recall == 1.0
            and refusal_correct
            and unsupported_rate == 0.0
        )

        results.append(
            EvalCaseResult(
                id=case.id,
                tenant_id=case.tenant_id,
                question=case.question,
                passed=passed,
                latency_ms=latency_ms,
                answer_contains_score=contains,
                citation_precision=precision,
                citation_recall=recall,
                refusal_correct=refusal_correct,
                unsupported_claim_rate=unsupported_rate,
                response=response,
            )
        )

    latencies = [result.latency_ms for result in results]
    return EvalReport(
        dataset=str(dataset_path),
        case_count=len(results),
        passed_count=sum(1 for result in results if result.passed),
        answer_contains_score=mean([result.answer_contains_score for result in results]),
        citation_precision=mean([result.citation_precision for result in results]),
        citation_recall=mean([result.citation_recall for result in results]),
        refusal_accuracy=mean([1.0 if result.refusal_correct else 0.0 for result in results]),
        unsupported_claim_rate=mean([result.unsupported_claim_rate for result in results]),
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        results=results,
    )


def write_eval_report(report: EvalReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "latest_report.json"
    markdown_path = output_dir / "latest_report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown_report(report: EvalReport) -> str:
    lines = [
        "# AgentOps RAG Eval Report",
        "",
        f"- Dataset: `{report.dataset}`",
        f"- Cases: {report.case_count}",
        f"- Passed: {report.passed_count}/{report.case_count}",
        f"- Answer contains score: {report.answer_contains_score:.3f}",
        f"- Citation precision: {report.citation_precision:.3f}",
        f"- Citation recall: {report.citation_recall:.3f}",
        f"- Refusal accuracy: {report.refusal_accuracy:.3f}",
        f"- Unsupported claim rate: {report.unsupported_claim_rate:.3f}",
        f"- p50 latency: {report.p50_latency_ms:.2f} ms",
        f"- p95 latency: {report.p95_latency_ms:.2f} ms",
        "",
        "## Cases",
        "",
        "| ID | Passed | Refused | Contains | Precision | Recall | Latency ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for result in report.results:
        lines.append(
            "| "
            f"{result.id} | "
            f"{'yes' if result.passed else 'no'} | "
            f"{'yes' if result.response.refused else 'no'} | "
            f"{result.answer_contains_score:.3f} | "
            f"{result.citation_precision:.3f} | "
            f"{result.citation_recall:.3f} | "
            f"{result.latency_ms:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)
