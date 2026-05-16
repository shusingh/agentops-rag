from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    filename: str
    title: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    ingestion_job_id: str

