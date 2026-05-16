# Ingestion Failure

## What Went Wrong

An uploaded document fails during load, chunking, embedding, or indexing.

## Detection

- Document status becomes `failed`.
- A DLQ entry is written with failure stage and retry count.
- Chunk count remains zero.

## Trace Or Log Signal

Inspect `ingestion.job`, `ingestion.chunk`, `opensearch.indexing`, and `dlq.write`. The span attribute `error_stage` identifies where the failure happened.

## Reproduce Locally

Run:

```bash
python -m pytest tests/test_ingestion_dlq.py
```

## Fix Or Mitigate

- Keep ingestion idempotent.
- Store failure stage and retry count.
- Replay DLQ jobs only for the owning tenant.
- Add poison-message limits before production.
