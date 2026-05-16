# Model Timeout

## What Went Wrong

The model provider fails to return within the request budget.

## Detection

- `agent.model_call` duration exceeds the timeout budget.
- `/ask` latency p95 rises.
- Benchmark reports show increased failure rate or latency.

## Trace Or Log Signal

Inspect `agent.model_call` and parent `agent.runtime` spans. The model span should carry model name and tenant ID.

## Reproduce Locally

Replace the fake model seam with a test double that sleeps past the timeout budget, then run the agent runtime tests.

## Fix Or Mitigate

- Add per-call timeouts.
- Add model fallback.
- Return a refusal or retryable error rather than hanging.
- Track model latency separately from retrieval latency.
