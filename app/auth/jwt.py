from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.config import Settings


class TokenClaims(BaseModel):
    subject: str = Field(alias="sub")
    tenant_id: str
    expires_at: datetime = Field(alias="exp")


def create_access_token(
    *,
    subject: str,
    tenant_id: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.demo_token_ttl_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    try:
        return TokenClaims.model_validate(payload)
    except ValueError as exc:
        raise ValueError("Token is missing required tenant claims") from exc
