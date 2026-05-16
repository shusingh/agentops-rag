from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.auth.jwt import decode_access_token
from app.config import Settings, get_settings
from app.telemetry.tracing import traced_span

bearer_scheme = HTTPBearer(auto_error=False)


class TenantContext(BaseModel):
    tenant_id: str
    subject: str


async def get_current_tenant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TenantContext:
    with traced_span("auth.validation"):
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            claims = decode_access_token(credentials.credentials, settings)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        tenant = TenantContext(tenant_id=claims.tenant_id, subject=claims.subject)
        return tenant
