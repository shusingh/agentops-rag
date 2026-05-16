from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Protocol, cast
from uuid import uuid4

from fastapi import Depends, HTTPException, Response, status
from redis import Redis
from redis.exceptions import RedisError

from app.auth.dependencies import TenantContext, get_current_tenant
from app.config import Settings, get_settings
from app.telemetry.tracing import traced_span


@dataclass(frozen=True)
class RateLimitRule:
    endpoint: str
    limit: int
    window_seconds: int
    fail_open: bool


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_time: float
    degraded: bool = False


class RateLimiter(Protocol):
    def check(
        self, *, tenant_id: str, endpoint: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        ...


class RedisSlidingWindowRateLimiter:
    def __init__(self, redis_client: Redis, script_path: Path | None = None) -> None:
        self.redis_client = redis_client
        self.script = (script_path or default_script_path()).read_text(encoding="utf-8")

    def check(
        self, *, tenant_id: str, endpoint: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        now_ms = int(time.time() * 1000)
        key = f"rate_limit:{tenant_id}:{endpoint}"
        member = f"{now_ms}:{uuid4().hex}"
        raw = self.redis_client.eval(
            self.script,
            1,
            key,
            now_ms,
            window_seconds * 1000,
            limit,
            member,
        )
        allowed_raw, remaining_raw, reset_ms_raw = cast(list[int], raw)
        return RateLimitResult(
            allowed=bool(allowed_raw),
            remaining=int(remaining_raw),
            reset_time=int(reset_ms_raw) / 1000,
        )


class InMemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self.clock = clock or time.time
        self.events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(
        self, *, tenant_id: str, endpoint: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        now = self.clock()
        events = self.events[(tenant_id, endpoint)]
        while events and events[0] <= now - window_seconds:
            events.popleft()
        if len(events) >= limit:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=events[0] + window_seconds,
            )
        events.append(now)
        return RateLimitResult(
            allowed=True,
            remaining=limit - len(events),
            reset_time=now + window_seconds,
        )


class UnavailableRateLimiter:
    def check(
        self, *, tenant_id: str, endpoint: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        raise RedisError("Rate limiter backend unavailable")


def default_script_path() -> Path:
    return Path(__file__).parent / "lua" / "sliding_window.lua"


def get_rate_limiter(settings: Annotated[Settings, Depends(get_settings)]) -> RateLimiter:
    return RedisSlidingWindowRateLimiter(Redis.from_url(settings.redis_url, decode_responses=True))


def rule_for_endpoint(endpoint: str, settings: Settings) -> RateLimitRule:
    if endpoint == "ask":
        return RateLimitRule(
            endpoint=endpoint,
            limit=settings.rate_limit_ask_limit,
            window_seconds=settings.rate_limit_window_seconds,
            fail_open=True,
        )
    if endpoint == "documents":
        return RateLimitRule(
            endpoint=endpoint,
            limit=settings.rate_limit_documents_limit,
            window_seconds=settings.rate_limit_window_seconds,
            fail_open=False,
        )
    if endpoint == "evals_run":
        return RateLimitRule(
            endpoint=endpoint,
            limit=settings.rate_limit_evals_limit,
            window_seconds=settings.rate_limit_window_seconds,
            fail_open=False,
        )
    raise ValueError(f"Unknown rate-limited endpoint: {endpoint}")


def rate_limit_dependency(endpoint: str) -> Callable[..., Awaitable[RateLimitResult]]:
    async def dependency(
        response: Response,
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
        settings: Annotated[Settings, Depends(get_settings)],
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> RateLimitResult:
        rule = rule_for_endpoint(endpoint, settings)
        with traced_span(
            "rate_limit.check",
            tenant_id=tenant.tenant_id,
            endpoint=rule.endpoint,
            limit=rule.limit,
            window_seconds=rule.window_seconds,
        ):
            try:
                result = limiter.check(
                    tenant_id=tenant.tenant_id,
                    endpoint=rule.endpoint,
                    limit=rule.limit,
                    window_seconds=rule.window_seconds,
                )
            except RedisError as exc:
                if rule.fail_open:
                    response.headers["X-RateLimit-Degraded"] = "true"
                    return RateLimitResult(
                        allowed=True,
                        remaining=0,
                        reset_time=time.time() + rule.window_seconds,
                        degraded=True,
                    )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiter unavailable",
                ) from exc

        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_time))
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(int(result.reset_time)),
                },
            )
        return result

    return dependency
