# Architecture

AgentOps RAG is built around a FastAPI API, tenant-scoped auth, Postgres metadata, Redis Streams ingestion, OpenSearch hybrid retrieval, explicit agent orchestration, OpenTelemetry tracing, and local eval/benchmark tooling.

The codebase keeps external systems behind small adapters so unit tests remain deterministic while the deployment path still targets Postgres, Redis, and OpenSearch.

## Tracing

OpenTelemetry is configured during FastAPI app creation. In local development, spans are exported to the console by default so traces are visible in the terminal running `make dev`.

Set these environment variables to control local behavior:

```bash
TRACING_ENABLED=true
TRACING_CONSOLE_EXPORTER=true
```

Current span coverage:

- `auth.validation`
- `document.upload`
- `ingestion.enqueue`
- `ingestion.job`
- `ingestion.chunk`
- `opensearch.indexing`
- `dlq.write`
- `dlq.replay`
- `agent.runtime`
- `agent.planner`
- `retrieval.bm25_search`
- `retrieval.vector_search`
- `retrieval.score_fusion`
- `agent.model_call`
- `agent.critic`
- `agent.finalizer`

Important attributes include tenant ID, document ID, chunk count, top-k, retry count, model name, planner action, retrieval hit counts, and failure stage.
