from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.jwt import create_access_token
from app.config import get_settings
from app.db.models import Base
from app.db.session import get_db
from app.ingestion.pipeline import InMemoryIngestionQueue, get_ingestion_queue
from app.ingestion.schemas import IngestionJob
from app.main import app
from app.rate_limit.limiter import InMemoryRateLimiter, get_rate_limiter
from app.workers.dlq import InMemoryDLQ, get_dlq


def make_client() -> tuple[TestClient, InMemoryIngestionQueue, InMemoryDLQ]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    queue = InMemoryIngestionQueue()
    dlq = InMemoryDLQ()

    def override_db() -> Generator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_ingestion_queue] = lambda: queue
    app.dependency_overrides[get_dlq] = lambda: dlq
    app.dependency_overrides[get_rate_limiter] = lambda: InMemoryRateLimiter()
    return TestClient(app), queue, dlq


def token_for(tenant_id: str) -> str:
    return create_access_token(
        subject="user_123",
        tenant_id=tenant_id,
        settings=get_settings(),
    )


def test_upload_document_uses_tenant_from_jwt_and_enqueues_job() -> None:
    client, queue, _ = make_client()

    response = client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token_for('tenant_a')}"},
        files={"file": ("policy.txt", b"Policy text for ingestion.", "text/plain")},
        data={"title": "Policy", "tenant_id": "tenant_b"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["document"]["tenant_id"] == "tenant_a"
    assert body["document"]["status"] == "pending"
    assert len(queue.jobs) == 1
    assert queue.jobs[0].tenant_id == "tenant_a"
    assert queue.jobs[0].document_id == body["document"]["id"]


def test_list_documents_is_scoped_to_authenticated_tenant() -> None:
    client, _, _ = make_client()

    client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token_for('tenant_a')}"},
        files={"file": ("a.txt", b"Tenant A document.", "text/plain")},
    )
    client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token_for('tenant_b')}"},
        files={"file": ("b.txt", b"Tenant B document.", "text/plain")},
    )

    response = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token_for('tenant_a')}"},
    )

    assert response.status_code == 200
    documents = response.json()
    assert len(documents) == 1
    assert documents[0]["tenant_id"] == "tenant_a"
    assert documents[0]["filename"] == "a.txt"


def test_admin_dlq_list_and_replay_are_tenant_scoped() -> None:
    client, queue, dlq = make_client()
    entry = dlq.write(
        job=queue_job("job_123", "tenant_a", "doc_123"),
        failure_stage="index_document",
        error_message="boom",
    )

    tenant_b_response = client.get(
        "/admin/dlq",
        headers={"Authorization": f"Bearer {token_for('tenant_b')}"},
    )
    assert tenant_b_response.status_code == 200
    assert tenant_b_response.json() == []

    replay_response = client.post(
        "/admin/dlq/replay",
        headers={"Authorization": f"Bearer {token_for('tenant_a')}"},
        json={"dlq_id": entry.dlq_id},
    )

    assert replay_response.status_code == 200
    assert replay_response.json()["replayed"] is True
    assert len(queue.jobs) == 1
    assert queue.jobs[0].retry_count == 1

    app.dependency_overrides.clear()


def queue_job(job_id: str, tenant_id: str, document_id: str) -> IngestionJob:
    return IngestionJob(job_id=job_id, tenant_id=tenant_id, document_id=document_id)
