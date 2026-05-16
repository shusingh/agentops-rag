# Tenant Isolation Breach

## What Went Wrong

A tenant sees, retrieves, or replays data owned by another tenant.

## Detection

- Tenant isolation tests fail.
- Retrieval hits include more than one tenant ID.
- DLQ replay succeeds for a tenant that does not own the DLQ entry.

## Trace Or Log Signal

Every relevant span carries `tenant_id`. Inspect `auth.validation`, `retrieval.*`, `document.upload`, and `dlq.replay` for mismatched tenant attributes.

## Reproduce Locally

Run:

```bash
python -m pytest tests/test_tenant_isolation.py tests/test_documents.py tests/test_hybrid_retrieval.py
```

## Fix Or Mitigate

- Treat JWT tenant ID as authoritative.
- Ignore request-body tenant IDs.
- Apply tenant filters at every storage and retrieval boundary.
- Keep cross-tenant tests mandatory in CI.
