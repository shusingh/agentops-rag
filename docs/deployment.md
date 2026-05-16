# Deployment

## Local

Local development uses Docker Compose for infrastructure:

```bash
make docker-up
make dev
```

Services:

- Postgres for document metadata
- Redis for ingestion streams, DLQ, and rate limits
- OpenSearch for BM25 and vector retrieval

## AWS Shape

A production AWS deployment would map local dependencies to managed services:

- API: ECS Fargate, EKS, or App Runner
- Postgres: Amazon RDS for PostgreSQL
- Redis: Amazon ElastiCache for Redis
- OpenSearch: Amazon OpenSearch Service
- Secrets: AWS Secrets Manager or SSM Parameter Store
- Traces: OTLP collector to AWS X-Ray, Grafana Tempo, Honeycomb, or Datadog
- Logs: CloudWatch Logs with structured JSON

## Worker Scaling

Ingestion workers should scale independently from the API. Worker concurrency should be bounded by embedding provider throughput, OpenSearch indexing capacity, and Redis stream lag.

## Secrets

Never bake secrets into images. Required secrets include JWT signing key, model provider keys, managed database credentials, and trace exporter credentials.

## Release Gates

Before promotion:

- unit tests pass
- lint and mypy pass
- offline eval report does not regress
- benchmark latency/failure thresholds hold
- tenant isolation tests pass
