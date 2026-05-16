from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.auth.dependencies import TenantContext, get_current_tenant
from app.auth.jwt import create_access_token
from app.config import get_settings
from app.tenants.isolation import assert_tenant_access, tenant_id_from_context


@dataclass
class Resource:
    tenant_id: str


class TenantOverrideAttempt(BaseModel):
    tenant_id: str


def test_assert_tenant_access_allows_matching_tenant() -> None:
    tenant = TenantContext(tenant_id="tenant_a", subject="user_123")

    assert_tenant_access(Resource(tenant_id="tenant_a"), tenant)


def test_assert_tenant_access_rejects_cross_tenant_resource() -> None:
    tenant = TenantContext(tenant_id="tenant_a", subject="user_123")

    with pytest.raises(PermissionError):
        assert_tenant_access(Resource(tenant_id="tenant_b"), tenant)


def test_tenant_id_from_jwt_cannot_be_overridden_by_request_body() -> None:
    probe_app = FastAPI()

    @probe_app.post("/probe")
    async def probe(
        payload: TenantOverrideAttempt,
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    ) -> dict[str, str]:
        return {
            "body_tenant_id": payload.tenant_id,
            "effective_tenant_id": tenant_id_from_context(tenant),
        }

    settings = get_settings()
    token = create_access_token(
        subject="user_123",
        tenant_id="tenant_from_token",
        settings=settings,
    )
    client = TestClient(probe_app)

    response = client.post(
        "/probe",
        json={"tenant_id": "tenant_from_body"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "body_tenant_id": "tenant_from_body",
        "effective_tenant_id": "tenant_from_token",
    }
