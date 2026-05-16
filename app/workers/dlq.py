from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from pydantic import BaseModel, Field
from redis import Redis

from app.config import get_settings
from app.ingestion.pipeline import IngestionQueue
from app.ingestion.schemas import IngestionJob
from app.telemetry.tracing import traced_span

DLQ_STREAM = "agentops:ingestion:dlq"


class DLQEntry(BaseModel):
    dlq_id: str
    job_id: str
    tenant_id: str
    document_id: str
    failure_stage: str
    error_message: str
    retry_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DeadLetterQueue(Protocol):
    def write(self, *, job: IngestionJob, failure_stage: str, error_message: str) -> DLQEntry:
        ...

    def list(self, *, tenant_id: str) -> list[DLQEntry]:
        ...

    def replay(self, *, dlq_id: str, tenant_id: str, queue: IngestionQueue) -> IngestionJob:
        ...


class InMemoryDLQ:
    def __init__(self) -> None:
        self.entries: list[DLQEntry] = []

    def write(self, *, job: IngestionJob, failure_stage: str, error_message: str) -> DLQEntry:
        with traced_span(
            "dlq.write",
            tenant_id=job.tenant_id,
            document_id=job.document_id,
            retry_count=job.retry_count,
            error_stage=failure_stage,
        ):
            entry = DLQEntry(
                dlq_id=f"dlq_{len(self.entries) + 1}",
                job_id=job.job_id,
                tenant_id=job.tenant_id,
                document_id=job.document_id,
                failure_stage=failure_stage,
                error_message=error_message,
                retry_count=job.retry_count,
            )
            self.entries.append(entry)
            return entry

    def list(self, *, tenant_id: str) -> list[DLQEntry]:
        return [entry for entry in self.entries if entry.tenant_id == tenant_id]

    def replay(self, *, dlq_id: str, tenant_id: str, queue: IngestionQueue) -> IngestionJob:
        with traced_span("dlq.replay", tenant_id=tenant_id, dlq_id=dlq_id):
            for index, entry in enumerate(self.entries):
                if entry.dlq_id == dlq_id and entry.tenant_id == tenant_id:
                    self.entries.pop(index)
                    job = IngestionJob(
                        job_id=entry.job_id,
                        tenant_id=entry.tenant_id,
                        document_id=entry.document_id,
                        retry_count=entry.retry_count + 1,
                    )
                    queue.enqueue(job)
                    return job
            raise KeyError("DLQ entry not found for authenticated tenant")


class RedisDLQ:
    def __init__(self, redis_client: Redis, stream_name: str = DLQ_STREAM) -> None:
        self.redis_client = redis_client
        self.stream_name = stream_name

    def write(self, *, job: IngestionJob, failure_stage: str, error_message: str) -> DLQEntry:
        with traced_span(
            "dlq.write",
            tenant_id=job.tenant_id,
            document_id=job.document_id,
            retry_count=job.retry_count,
            error_stage=failure_stage,
        ):
            entry = DLQEntry(
                dlq_id="pending",
                job_id=job.job_id,
                tenant_id=job.tenant_id,
                document_id=job.document_id,
                failure_stage=failure_stage,
                error_message=error_message,
                retry_count=job.retry_count,
            )
            stream_id = self.redis_client.xadd(self.stream_name, {"entry": entry.model_dump_json()})
            entry.dlq_id = (
                stream_id.decode("utf-8") if isinstance(stream_id, bytes) else str(stream_id)
            )
            return entry

    def list(self, *, tenant_id: str) -> list[DLQEntry]:
        entries: list[DLQEntry] = []
        stream_entries = cast(
            list[tuple[str | bytes, dict[str, str]]],
            self.redis_client.xrange(self.stream_name, min="-", max="+"),
        )
        for stream_id, fields in stream_entries:
            raw = fields.get("entry") if isinstance(fields, dict) else None
            if raw is None:
                continue
            entry = DLQEntry.model_validate(json.loads(raw))
            entry.dlq_id = (
                stream_id.decode("utf-8") if isinstance(stream_id, bytes) else str(stream_id)
            )
            if entry.tenant_id == tenant_id:
                entries.append(entry)
        return entries

    def replay(self, *, dlq_id: str, tenant_id: str, queue: IngestionQueue) -> IngestionJob:
        with traced_span("dlq.replay", tenant_id=tenant_id, dlq_id=dlq_id):
            entries = cast(
                list[tuple[str | bytes, dict[str, Any]]],
                self.redis_client.xrange(self.stream_name, min=dlq_id, max=dlq_id),
            )
            if not entries:
                raise KeyError("DLQ entry not found for authenticated tenant")

            _, fields = entries[0]
            raw = fields.get("entry")
            if raw is None:
                raise KeyError("DLQ entry is missing payload")
            entry = DLQEntry.model_validate(json.loads(raw))
            if entry.tenant_id != tenant_id:
                raise KeyError("DLQ entry not found for authenticated tenant")

            job = IngestionJob(
                job_id=entry.job_id,
                tenant_id=entry.tenant_id,
                document_id=entry.document_id,
                retry_count=entry.retry_count + 1,
            )
            queue.enqueue(job)
            self.redis_client.xdel(self.stream_name, dlq_id)
            return job


def get_dlq() -> DeadLetterQueue:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return RedisDLQ(redis_client, stream_name=DLQ_STREAM)
