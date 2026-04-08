"""Agent module Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Session Schemas
# =============================================================================


class AgentSessionBase(BaseModel):
    """Base schema for Agent Session"""

    title: str | None = Field(None, max_length=255)
    mode: str = Field(default="assistant")
    kb_ids: list[str] = Field(default_factory=list)


class AgentSessionCreate(AgentSessionBase):
    """Schema for creating Agent Session"""

    pass


class AgentSessionResponse(AgentSessionBase):
    """Schema for Agent Session response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Message Schemas
# =============================================================================


class AgentMessageResponse(BaseModel):
    """Schema for Agent Message response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    run_id: str | None = None
    role: str
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


# =============================================================================
# Step Schemas
# =============================================================================


class AgentStepResponse(BaseModel):
    """Schema for Agent Step response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    run_id: str | None = None
    step_index: int
    type: str
    name: str | None = None
    input: dict = Field(default_factory=dict)
    output: dict | None = None
    status: str
    error: str | None = None
    latency_ms: int | None = None
    created_at: datetime


# =============================================================================
# Run Schemas (Phase 2)
# =============================================================================


class AgentRunRequest(BaseModel):
    """Schema for running agent (chat request)"""

    input: str = Field(..., min_length=1, description="User input")
    stream: bool = Field(default=True, description="Enable SSE streaming")
    debug: bool = Field(default=False, description="Include debug info")
    mcp_server_ids: list[str] = Field(
        default_factory=list, description="MCP server IDs to use for this run"
    )


class AgentRunResponse(BaseModel):
    """Schema for non-streaming agent response"""

    session_id: str
    run_id: str
    output: str
    summary: str | None = None
    steps: list[dict] = Field(default_factory=list)


class AgentRunDetailResponse(BaseModel):
    """Schema for run detail (GET /runs/{id})"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    type: str
    status: str
    input: str
    output: str | None = None
    error: str | None = None
    last_step_index: int | None = None
    resumable: bool
    trace_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunStepsResponse(BaseModel):
    """Schema for run steps (GET /runs/{id}/steps)"""

    run_id: str
    steps: list[AgentStepResponse]


class AgentResumeRequest(BaseModel):
    """Schema for resuming a run"""

    input: str | None = Field(
        None, description="New input if continuing with different query"
    )


class AgentStopResponse(BaseModel):
    """Schema for stopping a run"""

    id: str
    status: str
    message: str = "Run stopped"


# =============================================================================
# AgentConfig Schemas (Phase 4)
# =============================================================================


class AgentConfigToolCreate(BaseModel):
    """Schema for creating an agent config tool link"""

    tool_name: str = Field(
        ..., description="Tool name (calculator, datetime, websearch)"
    )
    tool_config: dict = Field(
        default_factory=dict, description="Tool-specific configuration"
    )
    enabled: bool = Field(default=True)


class AgentConfigToolUpdate(BaseModel):
    """Schema for updating an agent config tool"""

    tool_config: dict | None = None
    enabled: bool | None = None


class AgentConfigToolResponse(BaseModel):
    """Schema for agent config tool response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: str
    tool_name: str
    tool_config: dict
    enabled: bool


class AgentConfigMCPCreate(BaseModel):
    """Schema for linking an MCP server to a config"""

    mcp_server_id: str = Field(..., description="MCP server ID to link")


class AgentConfigMCPResponse(BaseModel):
    """Schema for agent config MCP link response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: str
    mcp_server_id: str


class AgentConfigKBCreate(BaseModel):
    """Schema for linking a knowledge base to a config"""

    kb_id: str = Field(..., description="Knowledge base ID")
    kb_config: dict = Field(
        default_factory=dict, description="KB-specific config (top_k, etc)"
    )


class AgentConfigKBResponse(BaseModel):
    """Schema for agent config KB link response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: str
    kb_id: str
    kb_config: dict


class AgentConfigBase(BaseModel):
    """Base schema for AgentConfig"""

    name: str = Field(..., max_length=100)
    description: str | None = None
    llm_model_id: str | None = None
    agent_type: str = Field(default="simple")
    max_loop: int = Field(default=5)
    system_prompt: str | None = None
    enabled: bool = Field(default=True)


class AgentConfigCreate(AgentConfigBase):
    """Schema for creating AgentConfig"""

    pass


class AgentConfigUpdate(BaseModel):
    """Schema for updating AgentConfig"""

    name: str | None = None
    description: str | None = None
    llm_model_id: str | None = None
    agent_type: str | None = None
    max_loop: int | None = None
    system_prompt: str | None = None
    enabled: bool | None = None


class AgentConfigResponse(AgentConfigBase):
    """Schema for AgentConfig response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    created_at: datetime
    updated_at: datetime


class AgentConfigDetailResponse(AgentConfigResponse):
    """Schema for AgentConfig with full details (tools, MCP, KB links)"""

    tools: list[AgentConfigToolResponse] = Field(default_factory=list)
    mcp_servers: list[AgentConfigMCPResponse] = Field(default_factory=list)
    kbs: list[AgentConfigKBResponse] = Field(default_factory=list)


# =============================================================================
# MCP Server Schemas (Phase 4)
# =============================================================================


class AgentMCPServerBase(BaseModel):
    """Base schema for MCP server"""

    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=500)
    headers: dict | None = None
    transport: str = Field(default="streamable_http")
    enabled: bool = Field(default=True)


class AgentMCPServerCreate(AgentMCPServerBase):
    """Schema for creating MCP server"""

    pass


class AgentMCPServerUpdate(BaseModel):
    """Schema for updating MCP server"""

    name: str | None = None
    url: str | None = None
    headers: dict | None = None
    transport: str | None = None
    enabled: bool | None = None


class AgentMCPServerResponse(AgentMCPServerBase):
    """Schema for MCP server response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    created_at: datetime
    updated_at: datetime


class AgentMCPServerTestResponse(BaseModel):
    """Schema for MCP server connection test"""

    success: bool
    message: str
    tools_count: int = 0


# =============================================================================
# Builtin Tools Schema (Phase 4)
# =============================================================================


class BuiltinToolSchema(BaseModel):
    """Schema for built-in tool definition"""

    name: str
    description: str
    has_config: bool
    input_schema: dict
    config_schema: dict | None = None


class BuiltinToolsResponse(BaseModel):
    """Schema for listing all built-in tools"""

    tools: list[BuiltinToolSchema]


# =============================================================================
# Session Config Binding (Phase 4)
# =============================================================================


class AgentSessionConfigUpdate(BaseModel):
    """Schema for updating session's config_id binding"""

    config_id: str | None = Field(
        None,
        description="AgentConfig ID to bind, or null to unbind",
    )
