# Eval Methodology

The eval harness reads JSONL rows from `evals/datasets/` and writes reports to `evals/expected/`.

Each row contains:

- case ID
- tenant ID
- question
- expected answer substrings
- expected citation document IDs
- expected refusal behavior

## Metrics

- `answer_contains_score`: fraction of required substrings present in the answer
- `citation_precision`: fraction of produced citations that are expected
- `citation_recall`: fraction of expected citation documents cited
- `refusal_accuracy`: whether refusal behavior matches expectation
- `unsupported_claim_rate`: rough rate of critic-reported unsupported claims
- `p50_latency_ms`
- `p95_latency_ms`

## Interpreting Reports

A high answer score with low citation recall is still a failure for this project. The system is judged on grounded answers, not just plausible text.

Refusal cases are first-class. If the evidence is missing, the correct behavior is to refuse rather than improvise.
