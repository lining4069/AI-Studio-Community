"""
Agent database models.

Provides Agent entities for conversational AI with tool-calling capabilities.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base
from app.utils.datetime_utils import now_utc


class KbRetrievalMode(StrEnum):
    """Knowledge base retrieval mode"""

    FORCE = "force"  # Always retrieve from KB (agent becomes RAG assistant)
    INTENT = "intent"  # LLM decides when to retrieve (KB as a tool)


# ============================================================================
# Web Search Configuration
# ============================================================================


class WebSearchProvider(StrEnum):
    """Web search provider type"""

    TAVILY = "tavily"
    ALIYUN = "aliyun"


class WebSearchConfig(Base):
    """Web Search Configuration Entity"""

    __tablename__ = "websearch_configs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(20), default=WebSearchProvider.TAVILY.value
    )
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Search settings
    search_count: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<WebSearchConfig(id={self.id}, name={self.name}, provider={self.provider})>"


# ============================================================================
# MCP Server Configuration
# ============================================================================


class McpConnectionType(StrEnum):
    """MCP connection type"""

    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class McpServer(Base):
    """MCP Server Configuration Entity"""

    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    connection_type: Mapped[str] = mapped_column(
        String(20), default=McpConnectionType.SSE.value
    )
    encrypted_auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<McpServer(id={self.id}, name={self.name})>"


# ============================================================================
# Agent Entity
# ============================================================================


class Agent(Base):
    """Agent Entity with tool-calling capabilities"""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM Configuration (per-agent isolated parameters)
    llm_model_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True
    )
    llm_temperature: Mapped[float] = mapped_column(Float, default=0.7)
    llm_max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    llm_top_p: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_timeout: Mapped[int] = mapped_column(Integer, default=120)

    # System prompt
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Knowledge Base mounting
    kb_retrieval_mode: Mapped[str] = mapped_column(
        String(20), default=KbRetrievalMode.INTENT.value
    )
    kb_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    # MCP servers to mount
    mcp_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Web search
    enable_websearch: Mapped[bool] = mapped_column(Boolean, default=False)
    websearch_config_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("websearch_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Agent behavior
    max_steps: Mapped[int] = mapped_column(Integer, default=20)
    return_raw_response: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name})>"


# ============================================================================
# Agent Session (Conversation History)
# ============================================================================


class AgentSession(Base):
    """Agent Session for conversation history"""

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Session grouping (one session per conversation thread)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    # Conversation messages
    messages: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    def __repr__(self):
        return f"<AgentSession(id={self.id}, agent_id={self.agent_id}, session_id={self.session_id})>"
