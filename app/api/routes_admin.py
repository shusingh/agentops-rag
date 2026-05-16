from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import TenantContext, get_current_tenant
from app.ingestion.pipeline import IngestionQueue, get_ingestion_queue
from app.ingestion.schemas import IngestionJob
from app.workers.dlq import DeadLetterQueue, DLQEntry, get_dlq

router = APIRouter(prefix="/admin", tags=["admin"])


class DLQReplayRequest(BaseModel):
    dlq_id: str


class DLQReplayResponse(BaseModel):
    replayed: bool
    job: IngestionJob


@router.get("/dlq", response_model=list[DLQEntry])
async def list_dlq(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    dlq: Annotated[DeadLetterQueue, Depends(get_dlq)],
) -> list[DLQEntry]:
    return dlq.list(tenant_id=tenant.tenant_id)


@router.post("/dlq/replay", response_model=DLQReplayResponse)
async def replay_dlq(
    request: DLQReplayRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    dlq: Annotated[DeadLetterQueue, Depends(get_dlq)],
    queue: Annotated[IngestionQueue, Depends(get_ingestion_queue)],
) -> DLQReplayResponse:
    try:
        job = dlq.replay(dlq_id=request.dlq_id, tenant_id=tenant.tenant_id, queue=queue)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DLQ entry not found",
        ) from exc
    return DLQReplayResponse(replayed=True, job=job)
