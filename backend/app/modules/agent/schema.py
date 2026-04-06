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

    user_id: int


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


class AgentMessageBase(BaseModel):
    """Base schema for Agent Message"""

    role: str
    content: str


class AgentMessageCreate(AgentMessageBase):
    """Schema for creating Agent Message"""

    session_id: str


class AgentMessageResponse(AgentMessageBase):
    """Schema for Agent Message response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
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
# Run Schemas
# =============================================================================


class AgentRunRequest(BaseModel):
    """Schema for running agent (chat request)"""

    input: str = Field(..., min_length=1, description="User input")
    stream: bool = Field(default=True, description="Enable SSE streaming")
    debug: bool = Field(default=False, description="Include debug info")


class AgentRunResponse(BaseModel):
    """Schema for non-streaming agent response"""

    session_id: str
    output: str
    summary: str | None = None
    steps: list[dict] = Field(default_factory=list)
