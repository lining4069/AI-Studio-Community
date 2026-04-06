"""Agent API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.common.responses import APIResponse
from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.agent.repository import AgentRepository
from app.modules.agent.schema import (
    AgentMessageResponse,
    AgentRunRequest,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentStepResponse,
)
from app.modules.agent.service import AgentService
from app.modules.llm_model.repository import LlmModelRepository


router = APIRouter()


def get_agent_repository(db: DBAsyncSession) -> AgentRepository:
    return AgentRepository(db)


def get_llm_model_repository(db: DBAsyncSession) -> LlmModelRepository:
    return LlmModelRepository(db)


def get_agent_service(
    repo: Annotated[AgentRepository, Depends(get_agent_repository)],
    llm_repo: Annotated[LlmModelRepository, Depends(get_llm_model_repository)],
) -> AgentService:
    return AgentService(repo, llm_repo)


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


# =============================================================================
# Session Endpoints
# =============================================================================


@router.post("/sessions", response_model=APIResponse[AgentSessionResponse], status_code=201)
async def create_session(
    data: AgentSessionCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new agent session."""
    session = await service.create_session(current_user.id, data)
    return APIResponse(data=session, message="Session created")


@router.get("/sessions/{session_id}", response_model=APIResponse[AgentSessionResponse])
async def get_session(
    session_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get a session by ID."""
    session = await service.get_session(session_id, current_user.id)
    return APIResponse(data=session)


@router.get("/sessions/{session_id}/messages", response_model=APIResponse[list])
async def get_messages(
    session_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get messages for a session."""
    messages = await service.get_messages(session_id, current_user.id, limit)
    return APIResponse(data=messages)


@router.get("/sessions/{session_id}/steps", response_model=APIResponse[list])
async def get_steps(
    session_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get execution steps for a session (for debugging/replay)."""
    steps = await service.get_steps(session_id, current_user.id)
    return APIResponse(data=steps)


# =============================================================================
# Run Endpoint
# =============================================================================


@router.post("/sessions/{session_id}/runs")
async def run_agent(
    session_id: str,
    request: AgentRunRequest,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """
    Run agent with user input.

    If stream=True (default), returns SSE event stream.
    Otherwise returns complete response.
    """
    if request.stream:
        return await service.stream_agent(session_id, current_user.id, request)
    else:
        result = await service.run_agent(session_id, current_user.id, request)
        return APIResponse(data=result)
