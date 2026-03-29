"""
Agent schemas for request/response validation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.agent.models import (
    KbRetrievalMode,
    McpConnectionType,
    WebSearchProvider,
)

# ============================================================================
# WebSearch Config Schemas
# ============================================================================


class WebSearchConfigBase(BaseModel):
    """Base schema for WebSearchConfig"""

    name: str = Field(..., min_length=1, max_length=255)
    provider: WebSearchProvider = Field(default=WebSearchProvider.TAVILY)
    encrypted_api_key: str | None = None
    search_count: int = Field(default=10, ge=1, le=50)
    is_active: bool = Field(default=True)


class WebSearchConfigCreate(WebSearchConfigBase):
    """Schema for creating WebSearchConfig"""

    pass


class WebSearchConfigUpdate(BaseModel):
    """Schema for updating WebSearchConfig"""

    name: str | None = Field(None, min_length=1, max_length=255)
    provider: WebSearchProvider | None = None
    encrypted_api_key: str | None = None
    search_count: int | None = Field(None, ge=1, le=50)
    is_active: bool | None = None


class WebSearchConfigResponse(WebSearchConfigBase):
    """Schema for WebSearchConfig response"""

    id: str
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# MCP Server Schemas
# ============================================================================


class McpServerBase(BaseModel):
    """Base schema for MCP Server"""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=1000)
    connection_type: McpConnectionType = Field(default=McpConnectionType.SSE)
    encrypted_auth_token: str | None = None
    enabled: bool = Field(default=True)


class McpServerCreate(McpServerBase):
    """Schema for creating MCP Server"""

    pass


class McpServerUpdate(BaseModel):
    """Schema for updating MCP Server"""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=1000)
    connection_type: McpConnectionType | None = None
    encrypted_auth_token: str | None = None
    enabled: bool | None = None


class McpServerResponse(McpServerBase):
    """Schema for MCP Server response"""

    id: str
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Agent Schemas
# ============================================================================


class AgentBase(BaseModel):
    """Base schema for Agent"""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    # LLM Configuration
    llm_model_id: str | None = None
    llm_temperature: float = Field(default=0.7, ge=0, le=2)
    llm_max_tokens: int = Field(default=2048, ge=1)
    llm_top_p: float | None = Field(None, ge=0, le=1)
    llm_timeout: int = Field(default=120, ge=10)

    # System prompt
    system_prompt: str | None = None

    # Knowledge Base mounting
    kb_retrieval_mode: KbRetrievalMode = Field(default=KbRetrievalMode.INTENT)
    kb_ids: list[str] = Field(default_factory=list)

    # MCP servers
    mcp_ids: list[str] = Field(default_factory=list)

    # Web search
    enable_websearch: bool = Field(default=False)
    websearch_config_id: str | None = None

    # Agent behavior
    max_steps: int = Field(default=20, ge=1, le=100)
    return_raw_response: bool = Field(default=False)


class AgentCreate(AgentBase):
    """Schema for creating Agent"""

    pass


class AgentUpdate(BaseModel):
    """Schema for updating Agent"""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

    # LLM Configuration
    llm_model_id: str | None = None
    llm_temperature: float | None = Field(None, ge=0, le=2)
    llm_max_tokens: int | None = Field(None, ge=1)
    llm_top_p: float | None = Field(None, ge=0, le=1)
    llm_timeout: int | None = Field(None, ge=10)

    # System prompt
    system_prompt: str | None = None

    # Knowledge Base mounting
    kb_retrieval_mode: KbRetrievalMode | None = None
    kb_ids: list[str] | None = None

    # MCP servers
    mcp_ids: list[str] | None = None

    # Web search
    enable_websearch: bool | None = None
    websearch_config_id: str | None = None

    # Agent behavior
    max_steps: int | None = Field(None, ge=1, le=100)
    return_raw_response: bool | None = None

    is_active: bool | None = None


class AgentResponse(AgentBase):
    """Schema for Agent response"""

    id: str
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Chat Schemas
# ============================================================================


class ChatMessage(BaseModel):
    """Chat message in a conversation"""

    role: str = Field(..., description="Role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    tool_calls: list[dict[str, Any]] | None = Field(
        None, description="Tool calls made by assistant"
    )
    tool_call_id: str | None = Field(
        None, description="Tool call ID for tool responses"
    )


class ChatRequest(BaseModel):
    """Request schema for chat with agent"""

    agent_id: str = Field(..., description="Agent ID to use")
    messages: list[ChatMessage] = Field(..., description="Conversation messages")
    session_id: str | None = Field(
        None, description="Session ID for conversation continuity"
    )
    stream: bool = Field(default=True, description="Enable streaming response")


class ToolCallResult(BaseModel):
    """Result of a tool execution"""

    tool_call_id: str
    tool_name: str
    content: str
    error: str | None = None


class ChatResponse(BaseModel):
    """Response schema for non-streaming chat"""

    session_id: str
    message: str
    tool_calls: list[ToolCallResult] | None = None
    sources: list[str] = Field(default_factory=list)


# ============================================================================
# Tool Schemas
# ============================================================================


class ToolDefinition(BaseModel):
    """Tool definition for LLM function calling"""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(..., description="JSON Schema for parameters")


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool directly"""

    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResponse(BaseModel):
    """Response from tool execution"""

    tool_name: str
    content: str
    error: str | None = None
