# Rate Limit Exceeded

## What Went Wrong

A tenant exceeds the allowed request rate for an expensive endpoint.

## Detection

- The API returns `429 Rate limit exceeded`.
- Response headers include `X-RateLimit-Remaining` and `X-RateLimit-Reset`.
- `rate_limit.check` spans show the tenant, endpoint, limit, and window.

## Trace Or Log Signal

Inspect `rate_limit.check` spans for endpoint-specific limits. If Redis is unavailable, `/ask` includes `X-RateLimit-Degraded: true`, while `/documents` and `/evals/run` return `503`.

## Reproduce Locally

Run:

```bash
python -m pytest tests/test_rate_limit.py
```

## Fix Or Mitigate

- Increase tenant quota only with cost awareness.
- Add separate limits for interactive and batch workloads.
- Alert on degraded fail-open behavior for `/ask`.
