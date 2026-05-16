from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import TenantContext, get_current_tenant
from app.auth.jwt import create_access_token
from app.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class DemoTokenRequest(BaseModel):
    tenant_id: str = Field(default="demo", min_length=1, max_length=120)
    subject: str = Field(default="demo-user", min_length=1, max_length=120)


class DemoTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    expires_in_minutes: int


class WhoAmIResponse(BaseModel):
    tenant_id: str
    subject: str


@router.post("/demo-token", response_model=DemoTokenResponse)
async def create_demo_token(
    request: DemoTokenRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DemoTokenResponse:
    token = create_access_token(
        subject=request.subject,
        tenant_id=request.tenant_id,
        settings=settings,
    )
    return DemoTokenResponse(
        access_token=token,
        tenant_id=request.tenant_id,
        expires_in_minutes=settings.demo_token_ttl_minutes,
    )


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> WhoAmIResponse:
    return WhoAmIResponse(tenant_id=tenant.tenant_id, subject=tenant.subject)
