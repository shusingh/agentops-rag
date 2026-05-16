from typing import Protocol

from app.auth.dependencies import TenantContext


class TenantOwned(Protocol):
    tenant_id: str


def assert_tenant_access(resource: TenantOwned, tenant: TenantContext) -> None:
    if resource.tenant_id != tenant.tenant_id:
        raise PermissionError("Resource does not belong to the authenticated tenant")


def tenant_id_from_context(tenant: TenantContext) -> str:
    return tenant.tenant_id
