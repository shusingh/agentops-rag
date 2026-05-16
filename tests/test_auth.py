from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.config import get_settings
from app.main import app


def test_demo_token_can_authenticate_tenant() -> None:
    client = TestClient(app)

    token_response = client.post(
        "/auth/demo-token",
        json={"tenant_id": "tenant_a", "subject": "user_123"},
    )

    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    whoami_response = client.get(
        "/auth/whoami",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert whoami_response.status_code == 200
    assert whoami_response.json() == {"tenant_id": "tenant_a", "subject": "user_123"}


def test_missing_bearer_token_is_rejected() -> None:
    client = TestClient(app)

    response = client.get("/auth/whoami")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_expired_token_is_rejected() -> None:
    client = TestClient(app)
    settings = get_settings()
    token = create_access_token(
        subject="user_123",
        tenant_id="tenant_a",
        settings=settings,
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get(
        "/auth/whoami",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"
