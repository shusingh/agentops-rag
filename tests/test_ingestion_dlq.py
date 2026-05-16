from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Document
from app.ingestion.schemas import IngestionJob
from app.workers.dlq import InMemoryDLQ
from app.workers.ingestion_worker import InMemoryChunkIndex, process_ingestion_job


def make_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def test_worker_indexes_document_and_marks_it_indexed() -> None:
    db = make_session()
    document = Document(
        id="doc_123",
        tenant_id="tenant_a",
        filename="policy.txt",
        title="Policy",
        content_text="This policy requires audit logging for administrative actions.",
        status="pending",
    )
    db.add(document)
    db.commit()
    dlq = InMemoryDLQ()
    index = InMemoryChunkIndex()

    count = process_ingestion_job(
        db=db,
        job=IngestionJob(job_id="job_123", tenant_id="tenant_a", document_id="doc_123"),
        index=index,
        dlq=dlq,
    )

    refreshed = db.get(Document, "doc_123")
    assert count == 1
    assert refreshed is not None
    assert refreshed.status == "indexed"
    assert refreshed.chunk_count == 1
    assert len(index.chunks) == 1
    assert dlq.list(tenant_id="tenant_a") == []


def test_worker_writes_failed_job_to_dlq() -> None:
    db = make_session()
    dlq = InMemoryDLQ()
    index = InMemoryChunkIndex()

    count = process_ingestion_job(
        db=db,
        job=IngestionJob(job_id="job_404", tenant_id="tenant_a", document_id="missing"),
        index=index,
        dlq=dlq,
    )

    entries = dlq.list(tenant_id="tenant_a")
    assert count == 0
    assert len(entries) == 1
    assert entries[0].failure_stage == "load_document"
    assert entries[0].document_id == "missing"


def test_dlq_replay_is_tenant_scoped() -> None:
    dlq = InMemoryDLQ()
    queue = InMemoryQueue()
    entry = dlq.write(
        job=IngestionJob(job_id="job_123", tenant_id="tenant_a", document_id="doc_123"),
        failure_stage="index_document",
        error_message="boom",
    )

    try:
        dlq.replay(dlq_id=entry.dlq_id, tenant_id="tenant_b", queue=queue)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected cross-tenant replay to be rejected")

    replayed = dlq.replay(dlq_id=entry.dlq_id, tenant_id="tenant_a", queue=queue)

    assert replayed.retry_count == 1
    assert queue.job_ids == ["job_123"]
    assert dlq.list(tenant_id="tenant_a") == []


class InMemoryQueue:
    def __init__(self) -> None:
        self.job_ids: list[str] = []

    def enqueue(self, job: IngestionJob) -> str:
        self.job_ids.append(job.job_id)
        return job.job_id
