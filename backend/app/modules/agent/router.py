"""
Agent API router.

Provides endpoints for:
- Agent CRUD
- WebSearch Config CRUD
- MCP Server CRUD
- Chat with Agent
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.common.responses import APIResponse, PageData
from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.agent.repository import (
    AgentRepository,
    AgentSessionRepository,
    McpServerRepository,
    WebSearchConfigRepository,
)
from app.modules.agent.schema import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    ChatRequest,
    McpServerCreate,
    McpServerResponse,
    McpServerUpdate,
    WebSearchConfigCreate,
    WebSearchConfigResponse,
    WebSearchConfigUpdate,
)
from app.modules.agent.service import AgentService

router = APIRouter()


# ============================================================================
# Repository & Service Dependencies
# ============================================================================


def get_agent_repository(db: DBAsyncSession) -> AgentRepository:
    return AgentRepository(db)


def get_session_repository(db: DBAsyncSession) -> AgentSessionRepository:
    return AgentSessionRepository(db)


def get_ws_config_repository(db: DBAsyncSession) -> WebSearchConfigRepository:
    return WebSearchConfigRepository(db)


def get_mcp_repository(db: DBAsyncSession) -> McpServerRepository:
    return McpServerRepository(db)


def get_agent_service(
    agent_repo: Annotated[AgentRepository, Depends(get_agent_repository)],
    session_repo: Annotated[AgentSessionRepository, Depends(get_session_repository)],
    ws_config_repo: Annotated[
        WebSearchConfigRepository, Depends(get_ws_config_repository)
    ],
    mcp_repo: Annotated[McpServerRepository, Depends(get_mcp_repository)],
) -> AgentService:
    return AgentService(
        agent_repo=agent_repo,
        session_repo=session_repo,
        ws_config_repo=ws_config_repo,
        mcp_repo=mcp_repo,
    )


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


# ============================================================================
# Agent Endpoints
# ============================================================================


@router.post("", response_model=APIResponse[AgentResponse], status_code=201)
async def create_agent(
    data: AgentCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new Agent"""
    agent = await service.create_agent(current_user.id, data)
    return APIResponse(data=agent, message="创建成功")


@router.get("", response_model=APIResponse[PageData[AgentResponse]])
async def list_agents(
    current_user: CurrentUser,
    service: AgentServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all Agents for the current user"""
    items, total = await service.list_agents(current_user.id, page, page_size)
    return APIResponse(
        data=PageData(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/{agent_id}", response_model=APIResponse[AgentResponse])
async def get_agent(
    agent_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get a specific Agent"""
    agent = await service.get_agent(agent_id, current_user.id)
    return APIResponse(data=agent)


@router.put("/{agent_id}", response_model=APIResponse[AgentResponse])
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update an Agent"""
    agent = await service.update_agent(agent_id, current_user.id, data)
    return APIResponse(data=agent, message="更新成功")


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Delete an Agent and its sessions"""
    await service.delete_agent(agent_id, current_user.id)


# ============================================================================
# WebSearch Config Endpoints
# ============================================================================


@router.post(
    "/websearch-configs",
    response_model=APIResponse[WebSearchConfigResponse],
    status_code=201,
)
async def create_websearch_config(
    data: WebSearchConfigCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new WebSearchConfig"""
    config = await service.create_websearch_config(current_user.id, data)
    return APIResponse(data=config, message="创建成功")


@router.get(
    "/websearch-configs", response_model=APIResponse[PageData[WebSearchConfigResponse]]
)
async def list_websearch_configs(
    current_user: CurrentUser,
    service: AgentServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all WebSearchConfigs for the current user"""
    items, total = await service.list_websearch_configs(
        current_user.id, page, page_size
    )
    return APIResponse(
        data=PageData(items=items, total=total, page=page, page_size=page_size)
    )


@router.get(
    "/websearch-configs/{config_id}",
    response_model=APIResponse[WebSearchConfigResponse],
)
async def get_websearch_config(
    config_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get a specific WebSearchConfig"""
    config = await service.get_websearch_config(config_id, current_user.id)
    return APIResponse(data=config)


@router.put(
    "/websearch-configs/{config_id}",
    response_model=APIResponse[WebSearchConfigResponse],
)
async def update_websearch_config(
    config_id: str,
    data: WebSearchConfigUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update a WebSearchConfig"""
    config = await service.update_websearch_config(config_id, current_user.id, data)
    return APIResponse(data=config, message="更新成功")


@router.delete("/websearch-configs/{config_id}", status_code=204)
async def delete_websearch_config(
    config_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Delete a WebSearchConfig"""
    await service.delete_websearch_config(config_id, current_user.id)


# ============================================================================
# MCP Server Endpoints
# ============================================================================


@router.post(
    "/mcp-servers", response_model=APIResponse[McpServerResponse], status_code=201
)
async def create_mcp_server(
    data: McpServerCreate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Create a new MCP Server"""
    server = await service.create_mcp_server(current_user.id, data)
    return APIResponse(data=server, message="创建成功")


@router.get("/mcp-servers", response_model=APIResponse[PageData[McpServerResponse]])
async def list_mcp_servers(
    current_user: CurrentUser,
    service: AgentServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all MCP Servers for the current user"""
    items, total = await service.list_mcp_servers(current_user.id, page, page_size)
    return APIResponse(
        data=PageData(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/mcp-servers/{server_id}", response_model=APIResponse[McpServerResponse])
async def get_mcp_server(
    server_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Get a specific MCP Server"""
    server = await service.get_mcp_server(server_id, current_user.id)
    return APIResponse(data=server)


@router.put("/mcp-servers/{server_id}", response_model=APIResponse[McpServerResponse])
async def update_mcp_server(
    server_id: str,
    data: McpServerUpdate,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Update an MCP Server"""
    server = await service.update_mcp_server(server_id, current_user.id, data)
    return APIResponse(data=server, message="更新成功")


@router.delete("/mcp-servers/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: str,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """Delete an MCP Server"""
    await service.delete_mcp_server(server_id, current_user.id)


# ============================================================================
# Chat Endpoints
# ============================================================================


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: CurrentUser,
    service: AgentServiceDep,
):
    """
    Chat with an Agent.

    Supports streaming and non-streaming responses.
    Tool execution results are returned as SSE events.
    """
    if request.stream:
        # Streaming response
        async def generate():
            tool_buffer = []

            async for text_delta, tool_result in service.chat(current_user.id, request):
                if text_delta:
                    # Text chunk
                    data = json.dumps({"type": "text", "content": text_delta})
                    yield f"data: {data}\n\n"

                if tool_result:
                    # Tool result
                    data = json.dumps(
                        {
                            "type": "tool",
                            "tool_call_id": tool_result.tool_call_id,
                            "tool_name": tool_result.tool_name,
                            "content": tool_result.content,
                            "error": tool_result.error,
                        }
                    )
                    yield f"data: {data}\n\n"
                    tool_buffer.append(tool_result.tool_name)

            # Final message
            data = json.dumps(
                {
                    "type": "done",
                    "tool_calls": tool_buffer,
                }
            )
            yield f"data: {data}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )
    else:
        # Non-streaming response
        full_response = []
        tool_results = []

        async for text_delta, tool_result in service.chat(current_user.id, request):
            if text_delta:
                full_response.append(text_delta)
            if tool_result:
                tool_results.append(tool_result)

        return APIResponse(
            data={
                "session_id": request.session_id or "",
                "message": "".join(full_response),
                "tool_calls": tool_results,
            }
        )
