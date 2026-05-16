from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.runtime import AgentRuntime
from app.agents.schemas import AgentRequest, AgentResponse
from app.auth.dependencies import TenantContext, get_current_tenant
from app.rate_limit.limiter import RateLimitResult, rate_limit_dependency
from app.retrieval.embeddings import FakeEmbeddingClient
from app.retrieval.hybrid import InMemorySearchIndex

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_context: list[str] = Field(default_factory=list)


def get_agent_runtime() -> AgentRuntime:
    return AgentRuntime(index=InMemorySearchIndex(), embeddings=FakeEmbeddingClient())


@router.post("/ask", response_model=AgentResponse)
async def ask(
    request: AskRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    runtime: Annotated[AgentRuntime, Depends(get_agent_runtime)],
    _rate_limit: Annotated[RateLimitResult, Depends(rate_limit_dependency("ask"))],
) -> AgentResponse:
    return await runtime.run(
        AgentRequest(
            tenant_id=tenant.tenant_id,
            question=request.question,
            conversation_context=request.conversation_context,
        )
    )
