from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.models import Document
from app.ingestion.chunker import chunk_text
from app.ingestion.schemas import Chunk, IngestionJob
from app.telemetry.tracing import traced_span
from app.workers.dlq import DeadLetterQueue


class ChunkIndex(Protocol):
    def index_chunks(self, chunks: list[Chunk]) -> None:
        ...


class InMemoryChunkIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []

    def index_chunks(self, chunks: list[Chunk]) -> None:
        self.chunks.extend(chunks)


def process_ingestion_job(
    *,
    db: Session,
    job: IngestionJob,
    index: ChunkIndex,
    dlq: DeadLetterQueue,
) -> int:
    with traced_span(
        "ingestion.job",
        tenant_id=job.tenant_id,
        document_id=job.document_id,
        retry_count=job.retry_count,
    ) as span:
        document = db.get(Document, job.document_id)
        if document is None or document.tenant_id != job.tenant_id:
            span.set_attribute("error_stage", "load_document")
            dlq.write(job=job, failure_stage="load_document", error_message="Document not found")
            return 0

        try:
            document.status = "indexing"
            db.commit()

            with traced_span(
                "ingestion.chunk",
                tenant_id=document.tenant_id,
                document_id=document.id,
            ):
                chunks = chunk_text(
                    text=document.content_text,
                    document_id=document.id,
                    tenant_id=document.tenant_id,
                    source_title=document.title,
                    source_uri=document.filename,
                )
            span.set_attribute("chunk_count", len(chunks))
            if not chunks:
                raise ValueError("Document produced no chunks")

            with traced_span(
                "opensearch.indexing",
                tenant_id=document.tenant_id,
                document_id=document.id,
                chunk_count=len(chunks),
            ):
                index.index_chunks(chunks)

            document.status = "indexed"
            document.chunk_count = len(chunks)
            document.error_message = None
            document.indexed_at = datetime.now(UTC)
            db.commit()
            return len(chunks)
        except Exception as exc:
            db.rollback()
            document.status = "failed"
            document.error_message = str(exc)
            db.commit()
            span.set_attribute("error_stage", "index_document")
            dlq.write(job=job, failure_stage="index_document", error_message=str(exc))
            return 0
