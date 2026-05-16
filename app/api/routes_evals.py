from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import TenantContext, get_current_tenant
from app.rate_limit.limiter import RateLimitResult, rate_limit_dependency

router = APIRouter(prefix="/evals", tags=["evals"])


class EvalRunResponse(BaseModel):
    accepted: bool
    tenant_id: str
    message: str


@router.post("/run", response_model=EvalRunResponse)
async def run_evals(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    _rate_limit: Annotated[RateLimitResult, Depends(rate_limit_dependency("evals_run"))],
) -> EvalRunResponse:
    return EvalRunResponse(
        accepted=True,
        tenant_id=tenant.tenant_id,
        message="Eval execution endpoint is reserved for the Phase 6 local runner.",
    )
