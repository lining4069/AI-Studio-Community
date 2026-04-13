"""Agent API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.common.responses import APIResponse, PageData
from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.agent.repository import AgentRepository
from app.modules.agent.schema import (
    AgentConfigCreate,
    AgentConfigDetailResponse,
    AgentConfigKBCreate,
    AgentConfigKBResponse,
    AgentConfigMCPCreate,
    AgentConfigMCPResponse,
    AgentConfigResponse,
    AgentConfigToolCreate,
    AgentConfigToolResponse,
    AgentConfigToolUpdate,
    AgentConfigUpdate,
    AgentMCPServerCreate,
    AgentMCPServerResponse,
    AgentMCPServerTestResponse,
    AgentMCPServerUpdate,
    AgentRunDetailResponse,
    AgentRunRequest,
    AgentSessionConfigUpdate,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentStopResponse,
    BuiltinToolsResponse,
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


@router.post(
    "/sessions", response_model=APIResponse[AgentSessionResponse], status_code=201
)
async def create_session(
    data: AgentSessionCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new agent session."""
    session = await service.create_session(current_user.id, data)
    return APIResponse(data=session, message="Session created")


@router.get(
    "/sessions",
    response_model=APIResponse[PageData[AgentSessionResponse]],
)
async def list_sessions(
    current_user: CurrentUser,
    service: AgentServiceDep,
    config_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List sessions for the current user, optionally filtered by config."""
    data = await service.list_sessions_page(
        current_user.id,
        page=page,
        page_size=page_size,
        config_id=config_id,
    )
    return APIResponse(data=data)


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
# Run Endpoints (Phase 2)
# =============================================================================


@router.get("/runs/{run_id}", response_model=APIResponse[AgentRunDetailResponse])
async def get_run(
    run_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get a run by ID (includes ownership verification)."""
    run = await service.get_run(run_id, current_user.id)
    return APIResponse(data=run)


@router.get("/runs/{run_id}/steps", response_model=APIResponse[list])
async def get_run_steps(
    run_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get all steps for a run."""
    steps = await service.get_run_steps(run_id, current_user.id)
    return APIResponse(data=steps)


@router.post("/runs/{run_id}/resume")
async def resume_agent(
    run_id: str,
    request: AgentRunRequest,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """
    Resume an interrupted run from last successful step.

    Creates a new run that continues from where the original left off.
    Original run is marked as 'interrupted'.
    """
    return await service.resume_agent(run_id, current_user.id, request)


@router.post("/runs/{run_id}/stop", response_model=APIResponse[AgentStopResponse])
async def stop_run(
    run_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """
    Stop a running run (marks as interrupted).

    Note: This marks the run as interrupted. If the stream is still
    in progress, it will complete naturally. Future resume calls will
    see the interrupted status.
    """
    result = await service.stop_run(run_id, current_user.id)
    return APIResponse(data=result)


# =============================================================================
# Run Execution
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


# =============================================================================
# Session Config Binding (Phase 4)
# =============================================================================


@router.patch("/sessions/{session_id}/config", status_code=204)
async def update_session_config(
    session_id: str,
    data: AgentSessionConfigUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update session's config_id binding."""
    await service.update_session_config(session_id, current_user.id, data.config_id)


# =============================================================================
# Builtin Tools (Phase 4)
# =============================================================================


@router.get("/builtin-tools", response_model=APIResponse[BuiltinToolsResponse])
async def get_builtin_tools(service: AgentServiceDep):
    """Get all available built-in tools with their schemas."""
    tools = await service.get_builtin_tools()
    return APIResponse(data={"tools": tools})


# =============================================================================
# AgentConfig CRUD (Phase 4)
# =============================================================================


@router.post(
    "/configs",
    response_model=APIResponse[AgentConfigResponse],
    status_code=201,
)
async def create_config(
    data: AgentConfigCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new agent config."""
    config = await service.create_config(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        llm_model_id=data.llm_model_id,
        agent_type=data.agent_type,
        max_loop=data.max_loop,
        system_prompt=data.system_prompt,
        enabled=data.enabled,
    )
    return APIResponse(data=config, message="Config created")


@router.get("/configs", response_model=APIResponse[list[AgentConfigResponse]])
async def list_configs(
    service: AgentServiceDep,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List agent configs for current user."""
    configs, total = await service.list_configs(
        current_user.id, page=page, page_size=page_size
    )
    return APIResponse(data=configs, total=total)  # type: ignore[call-arg]


@router.get("/configs/{config_id}", response_model=APIResponse[AgentConfigDetailResponse])
async def get_config(
    config_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get an agent config by ID."""
    config = await service.get_config_detail(config_id, current_user.id)
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")
    return APIResponse(data=config)


@router.put("/configs/{config_id}", response_model=APIResponse[AgentConfigResponse])
async def update_config(
    config_id: str,
    data: AgentConfigUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update an agent config."""
    config = await service.update_config(
        config_id=config_id,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        llm_model_id=data.llm_model_id,
        agent_type=data.agent_type,
        max_loop=data.max_loop,
        system_prompt=data.system_prompt,
        enabled=data.enabled,
    )
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")
    return APIResponse(data=config)


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(
    config_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Delete an agent config."""
    deleted = await service.delete_config(config_id, current_user.id)
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")


# =============================================================================
# Config Tools (Phase 4)
# =============================================================================


@router.get(
    "/configs/{config_id}/tools",
    response_model=APIResponse[list[AgentConfigToolResponse]],
)
async def get_config_tools(
    config_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get all tools in a config."""
    # Verify ownership
    config = await service.get_config(config_id, current_user.id)
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")
    tools = await service.get_config_tools(config_id)
    return APIResponse(data=tools)


@router.post(
    "/configs/{config_id}/tools",
    response_model=APIResponse[AgentConfigToolResponse],
    status_code=201,
)
async def add_config_tool(
    config_id: str,
    data: AgentConfigToolCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Add a tool to a config."""
    # Verify ownership
    config = await service.get_config(config_id, current_user.id)
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")
    tool = await service.add_config_tool(
        config_id=config_id,
        tool_name=data.tool_name,
        tool_config=data.tool_config,
        enabled=data.enabled,
    )
    return APIResponse(data=tool, message="Tool added to config")


@router.put(
    "/configs/{config_id}/tools/{tool_id}",
    response_model=APIResponse[AgentConfigToolResponse],
)
async def update_config_tool(
    config_id: str,
    tool_id: int,
    data: AgentConfigToolUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update a tool in a config."""
    tool = await service.update_config_tool(
        config_id=config_id,
        user_id=current_user.id,
        tool_id=tool_id,
        tool_config=data.tool_config,
        enabled=data.enabled,
    )
    if not tool:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Tool not found")
    return APIResponse(data=tool)


@router.delete("/configs/{config_id}/tools/{tool_id}", status_code=204)
async def delete_config_tool(
    config_id: str,
    tool_id: int,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Remove a tool from a config."""
    deleted = await service.delete_config_tool(
        config_id=config_id,
        user_id=current_user.id,
        tool_id=tool_id,
    )
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Tool not found")


@router.get(
    "/configs/{config_id}/resolved-tools",
    response_model=APIResponse[dict],
)
async def get_resolved_tools(
    config_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get resolved tool list for debugging (shows what would be loaded)."""
    tools, warnings = await service.get_resolved_tools(config_id, current_user.id)
    return APIResponse(data={"tools": tools, "warnings": warnings})


# =============================================================================
# Config MCP Servers (Phase 4)
# =============================================================================


@router.post(
    "/configs/{config_id}/mcp-servers",
    response_model=APIResponse[AgentConfigMCPResponse],
    status_code=201,
)
async def link_mcp_server(
    config_id: str,
    data: AgentConfigMCPCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Link an MCP server to a config."""
    # Verify config ownership
    config = await service.get_config(config_id, current_user.id)
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")
    # Verify MCP server ownership
    mcp = await service.get_mcp_server(data.mcp_server_id, current_user.id)
    if not mcp:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="MCP server not found")
    link = await service.add_config_mcp_server(
        config_id=config_id,
        mcp_server_id=data.mcp_server_id,
    )
    return APIResponse(data=link, message="MCP server linked to config")


@router.delete("/configs/{config_id}/mcp-servers/{link_id}", status_code=204)
async def unlink_mcp_server(
    config_id: str,
    link_id: int,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Unlink an MCP server from a config."""
    deleted = await service.delete_config_mcp_server(
        config_id=config_id,
        user_id=current_user.id,
        link_id=link_id,
    )
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Link not found")


# =============================================================================
# Config KB Links (Phase 4)
# =============================================================================


@router.post(
    "/configs/{config_id}/kbs",
    response_model=APIResponse[AgentConfigKBResponse],
    status_code=201,
)
async def link_kb(
    config_id: str,
    data: AgentConfigKBCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Link a knowledge base to a config."""
    # Verify config ownership
    config = await service.get_config(config_id, current_user.id)
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Config not found")
    link = await service.add_config_kb(
        config_id=config_id,
        kb_id=data.kb_id,
        kb_config=data.kb_config,
    )
    return APIResponse(data=link, message="KB linked to config")


@router.delete("/configs/{config_id}/kbs/{link_id}", status_code=204)
async def unlink_kb(
    config_id: str,
    link_id: int,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Unlink a knowledge base from a config."""
    deleted = await service.delete_config_kb(
        config_id=config_id,
        user_id=current_user.id,
        link_id=link_id,
    )
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Link not found")


# =============================================================================
# MCP Server CRUD (Phase 4)
# =============================================================================


@router.post(
    "/mcp-servers",
    response_model=APIResponse[AgentMCPServerResponse],
    status_code=201,
)
async def create_mcp_server(
    data: AgentMCPServerCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new MCP server."""
    server = await service.create_mcp_server(
        user_id=current_user.id,
        name=data.name,
        transport=data.transport,
        url=data.url,
        headers=data.headers,
        command=data.command,
        args=data.args,
        env=data.env,
        cwd=data.cwd,
        enabled=data.enabled,
    )
    return APIResponse(data=server, message="MCP server created")


@router.get("/mcp-servers", response_model=APIResponse[list[AgentMCPServerResponse]])
async def list_mcp_servers(
    service: AgentServiceDep,
    current_user: CurrentUser,
):
    """List MCP servers for current user."""
    servers, total = await service.list_mcp_servers(current_user.id)
    return APIResponse(data=servers, total=total)  # type: ignore[call-arg]


@router.get(
    "/mcp-servers/{server_id}", response_model=APIResponse[AgentMCPServerResponse]
)
async def get_mcp_server(
    server_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get an MCP server by ID."""
    server = await service.get_mcp_server(server_id, current_user.id)
    if not server:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="MCP server not found")
    return APIResponse(data=server)


@router.put(
    "/mcp-servers/{server_id}", response_model=APIResponse[AgentMCPServerResponse]
)
async def update_mcp_server(
    server_id: str,
    data: AgentMCPServerUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update an MCP server."""
    server = await service.update_mcp_server(
        server_id=server_id,
        user_id=current_user.id,
        name=data.name,
        transport=data.transport,
        url=data.url,
        headers=data.headers,
        command=data.command,
        args=data.args,
        env=data.env,
        cwd=data.cwd,
        enabled=data.enabled,
    )
    if not server:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="MCP server not found")
    return APIResponse(data=server)


@router.delete("/mcp-servers/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Delete an MCP server."""
    deleted = await service.delete_mcp_server(server_id, current_user.id)
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="MCP server not found")


@router.post(
    "/mcp-servers/{server_id}/test",
    response_model=APIResponse[AgentMCPServerTestResponse],
)
async def test_mcp_server(
    server_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Test MCP server connection."""
    result = await service.test_mcp_server(server_id, current_user.id)
    return APIResponse(data=result)
