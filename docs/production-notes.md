# Production Notes

## Managed Services

Local Compose services should become managed Postgres, Redis, and OpenSearch in production. The code keeps these behind small boundaries so replacing local dependencies is an operational change rather than a rewrite.

## Secrets

Use a secret manager for JWT signing keys, model provider keys, database credentials, and trace exporter credentials. Rotate JWT keys with overlapping validity windows.

## Worker Scaling

Scale ingestion workers from queue lag and indexing latency. Track retries and DLQ growth separately from normal stream depth.

## Model Fallback

The model client is a protocol so production can add:

- per-call timeouts
- provider fallback
- circuit breakers
- tenant-specific budgets

## Offline Eval Gates

CI should run representative JSONL evals and fail on regressions in citation recall, refusal accuracy, unsupported claim rate, or latency thresholds.

## Retrieval Quality Drift

Monitor retrieval drift by tracking eval recall, top-k score distributions, refused-answer rate, and query categories over time.

## Rate Limiting Tradeoff

Rate limits are tenant-scoped and endpoint-scoped using Redis plus a Lua sliding-window script.

Protected endpoints:

- `/ask`
- `/documents`
- `/evals/run`

Redis unavailable behavior is explicit:

- `/ask` fails open and adds `X-RateLimit-Degraded: true`. This preserves user-facing Q&A availability during a Redis incident, while logs/traces still show degraded enforcement.
- `/documents` fails closed with `503`. Uploads can create ingestion and indexing work, so accepting unbounded uploads during a limiter outage is riskier.
- `/evals/run` fails closed with `503`. Evals are intentionally expensive and should not bypass quota controls.

In production, the fail-open `/ask` path should emit an alert if Redis is unavailable for more than a short grace period.
