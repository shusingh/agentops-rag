from fastapi.testclient import TestClient

from app.agents.schemas import AgentRequest, AgentResponse
from app.api.routes_ask import get_agent_runtime
from app.auth.jwt import create_access_token
from app.config import get_settings
from app.main import app
from app.rate_limit.limiter import (
    InMemoryRateLimiter,
    RateLimitResult,
    UnavailableRateLimiter,
    get_rate_limiter,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def token_for(tenant_id: str) -> str:
    return create_access_token(subject="user_123", tenant_id=tenant_id, settings=get_settings())


def test_in_memory_rate_limiter_allows_under_limit_and_blocks_over_limit() -> None:
    clock = Clock()
    limiter = InMemoryRateLimiter(clock=clock)

    first = limiter.check(tenant_id="tenant_a", endpoint="ask", limit=2, window_seconds=60)
    second = limiter.check(tenant_id="tenant_a", endpoint="ask", limit=2, window_seconds=60)
    third = limiter.check(tenant_id="tenant_a", endpoint="ask", limit=2, window_seconds=60)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert third.allowed is False
    assert third.reset_time == 1060.0


def test_rate_limiter_isolates_tenant_quotas() -> None:
    clock = Clock()
    limiter = InMemoryRateLimiter(clock=clock)

    tenant_a = limiter.check(tenant_id="tenant_a", endpoint="ask", limit=1, window_seconds=60)
    tenant_a_blocked = limiter.check(
        tenant_id="tenant_a", endpoint="ask", limit=1, window_seconds=60
    )
    tenant_b = limiter.check(tenant_id="tenant_b", endpoint="ask", limit=1, window_seconds=60)

    assert tenant_a.allowed is True
    assert tenant_a_blocked.allowed is False
    assert tenant_b.allowed is True


def test_ask_endpoint_returns_429_when_over_limit() -> None:
    limiter = OneAllowedLimiter()
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_agent_runtime] = lambda: RuntimeProbe()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token_for('tenant_a')}"}

    first = client.post("/ask", headers=headers, json={"question": "What is required?"})
    second = client.post("/ask", headers=headers, json={"question": "What is required?"})

    app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.status_code == 429


def test_ask_fails_open_when_rate_limiter_unavailable() -> None:
    app.dependency_overrides[get_rate_limiter] = lambda: UnavailableRateLimiter()
    app.dependency_overrides[get_agent_runtime] = lambda: RuntimeProbe()
    client = TestClient(app)

    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token_for('tenant_a')}"},
        json={"question": "What is required?"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Degraded"] == "true"


def test_evals_fail_closed_when_rate_limiter_unavailable() -> None:
    app.dependency_overrides[get_rate_limiter] = lambda: UnavailableRateLimiter()
    client = TestClient(app)

    response = client.post(
        "/evals/run",
        headers={"Authorization": f"Bearer {token_for('tenant_a')}"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"] == "Rate limiter unavailable"


class OneAllowedLimiter:
    def __init__(self) -> None:
        self.calls = 0

    def check(
        self, *, tenant_id: str, endpoint: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        self.calls += 1
        return RateLimitResult(
            allowed=self.calls == 1,
            remaining=0,
            reset_time=1000.0 + window_seconds,
        )


class RuntimeProbe:
    async def run(self, request: AgentRequest) -> AgentResponse:
        from app.agents.schemas import (
            AgentResponse,
            CriticFinding,
            PlannerAction,
            PlannerDecision,
        )
        from app.retrieval.schemas import HybridSearchSummary

        return AgentResponse(
            answer="ok",
            citations=[],
            refused=False,
            trace_id="trace_test",
            retrieval=HybridSearchSummary(top_k=5, bm25_hits=0, vector_hits=0),
            planner=PlannerDecision(
                action=PlannerAction.RETRIEVE,
                rationale="test",
                rewritten_query=request.question,
            ),
            critic=CriticFinding(supported=True, should_refuse=False, rationale="test"),
        )
