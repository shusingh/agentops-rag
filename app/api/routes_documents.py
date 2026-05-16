from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import DocumentResponse, DocumentUploadResponse
from app.auth.dependencies import TenantContext, get_current_tenant
from app.db.models import Document
from app.db.session import get_db
from app.ingestion.pipeline import IngestionQueue, get_ingestion_queue
from app.ingestion.schemas import IngestionJob
from app.rate_limit.limiter import RateLimitResult, rate_limit_dependency
from app.telemetry.tracing import traced_span

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[Session, Depends(get_db)],
    queue: Annotated[IngestionQueue, Depends(get_ingestion_queue)],
    _rate_limit: Annotated[RateLimitResult, Depends(rate_limit_dependency("documents"))],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    with traced_span("document.upload", tenant_id=tenant.tenant_id, filename=file.filename):
        raw = await file.read()
        try:
            content_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only UTF-8 text documents are supported in this phase",
            ) from exc

        if not content_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is empty",
            )

        document = Document(
            id=f"doc_{uuid4().hex}",
            tenant_id=tenant.tenant_id,
            filename=file.filename or "uploaded.txt",
            title=title or file.filename or "Untitled document",
            content_text=content_text,
            status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        job = IngestionJob(
            job_id=f"job_{uuid4().hex}",
            tenant_id=tenant.tenant_id,
            document_id=document.id,
        )
        with traced_span(
            "ingestion.enqueue",
            tenant_id=tenant.tenant_id,
            document_id=document.id,
            retry_count=job.retry_count,
        ):
            queue.enqueue(job)

        return DocumentUploadResponse(
            document=DocumentResponse.model_validate(document),
            ingestion_job_id=job.job_id,
        )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentResponse]:
    documents = db.scalars(
        select(Document).where(Document.tenant_id == tenant.tenant_id).order_by(Document.created_at)
    ).all()
    return [DocumentResponse.model_validate(document) for document in documents]
