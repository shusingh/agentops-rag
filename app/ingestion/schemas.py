from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class IngestionJob(BaseModel):
    job_id: str
    tenant_id: str
    document_id: str
    retry_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Chunk(BaseModel):
    document_id: str
    chunk_id: str
    tenant_id: str
    source_title: str
    source_uri: str
    text: str
    ordinal: int
