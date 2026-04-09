"""Agent system database models."""

import uuid
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import Base, TimestampMixin
from app.modules.agent.enums import AgentTypeMode


class AgentMode(StrEnum):
    """Agent running mode"""

    ASSISTANT = "assistant"
    AGENT = "agent"


class StepType(StrEnum):
    """Step execution type"""

    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"


class StepStatus(StrEnum):
    """Step execution status"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class AgentRunStatus(StrEnum):
    """Run execution status"""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"


# ============================================================================
# Agent Session
# ============================================================================


class AgentSession(Base, TimestampMixin):
    """
    Agent conversation session.

    Represents a single conversation session with memory (summary).
    Links to an AgentConfig for persistent configuration.
    """

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Session configuration (Phase 4: links to AgentConfig)
    config_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("agent_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default=AgentMode.ASSISTANT.value)

    # Light memory: conversation summary
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<AgentSession(id={self.id}, mode={self.mode})>"


# ============================================================================
# Agent Run (Phase 2)
# ============================================================================


class AgentRun(Base, TimestampMixin):
    """
    Agent run - a single execution instance.

    Represents one complete execution of the Agent (one /runs API request).
    Run status lifecycle: running -> success / error / interrupted

    Phase 4: config_snapshot stores the config at run time for reproducibility.
    """

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Execution type
    type: Mapped[str] = mapped_column(String(20), default="chat")

    # Core state
    status: Mapped[str] = mapped_column(
        String(20), default=AgentRunStatus.RUNNING.value
    )

    # Execution summary
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resume support
    last_step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Note: last_step_index is updated by service layer after each step success
    resumable: Mapped[bool] = mapped_column(default=True)

    # Traceability (for logs/observability)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Phase 4: Config snapshot for reproducibility
    # Frozen copy of AgentConfig at run time (not in Session to ensure run reproducibility)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self):
        return f"<AgentRun(id={self.id}, status={self.status})>"


# ============================================================================
# Agent Message
# ============================================================================


class AgentMessage(Base, TimestampMixin):
    """
    Agent conversation message.

    Stores user/assistant/system messages in a session.
    Run-owned: each message belongs to a specific run.
    """

    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Run ownership (Phase 2)
    run_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    def __repr__(self):
        return f"<AgentMessage(id={self.id}, role={self.role})>"


# ============================================================================
# Agent Step
# ============================================================================


class AgentStep(Base, TimestampMixin):
    """
    Agent execution step trace.

    Records each execution unit (LLM call, tool execution, retrieval).
    Used for replay, debug, and observability.
    """

    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Run ownership (Phase 2)
    run_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Execution order (critical for replay, unique per run)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Step classification
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # llm/tool/retrieval
    name: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # tool/model name

    # Input/Output (JSON for flexibility)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ReAct thought (for future Phase 3)
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Execution metadata
    status: Mapped[str] = mapped_column(String(20), default=StepStatus.PENDING.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Idempotency key for tool execution (Phase 2)
    # Format: sha256(f"{run_id}:{step_index}:{tool_name}")[:16]
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    def __repr__(self):
        return f"<AgentStep(id={self.id}, type={self.type}, status={self.status})>"


# ============================================================================
# Agent MCP Server (Phase 3, enhanced Phase 4)
# ============================================================================


class AgentMCPServer(Base, TimestampMixin):
    """
    MCP server configuration for Agent tools.

    Stores connection config for MCP servers that provide tools
    via the Model Context Protocol.

    Phase 4: Added user_id for ownership and isolation.
    Phase 5: Added stdio support fields (command, args, env, cwd).
    """

    __tablename__ = "agent_mcp_servers"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_mcp_server_user_name"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transport: Mapped[str] = mapped_column(String(20), default="streamable_http")

    # HTTP-based transport
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # stdio transport
    command: Mapped[str | None] = mapped_column(String(100), nullable=True)
    args: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    env: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    cwd: Mapped[str | None] = mapped_column(String(500), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self):
        return f"<AgentMCPServer(id={self.id}, name={self.name}, transport={self.transport})>"


# ============================================================================
# Agent Config (Phase 4)
# ============================================================================


class AgentConfig(Base, TimestampMixin):
    """
    Persistent configuration template for an Agent/Assistant.

    Defines which tools, MCP servers, knowledge bases, and LLM to use.
    Sessions reference a config to get consistent tool availability.

    Phase 4: Replaces system-wide tool loading with per-config selection.
    """

    __tablename__ = "agent_configs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM Configuration
    llm_model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Agent Behavior
    agent_type: Mapped[str] = mapped_column(
        String(20), default=AgentTypeMode.SIMPLE.value
    )
    max_loop: Mapped[int] = mapped_column(Integer, default=5)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relations
    tools: Mapped[list["AgentConfigTool"]] = relationship(
        back_populates="agent_config", cascade="all, delete-orphan"
    )
    mcp_links: Mapped[list["AgentConfigMCP"]] = relationship(
        back_populates="agent_config", cascade="all, delete-orphan"
    )
    kb_links: Mapped[list["AgentConfigKB"]] = relationship(
        back_populates="agent_config", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AgentConfig(id={self.id}, name={self.name}, agent_type={self.agent_type})>"


class AgentConfigTool(Base):
    """
    Association table for AgentConfig -> built-in tools.

    Stores per-tool configuration (e.g., websearch api_key).
    Unique constraint ensures no duplicate tool names per config.

    Phase 4: Replaces JSON array of tool names with proper relation.
    """

    __tablename__ = "agent_config_tools"
    __table_args__ = (
        UniqueConstraint("config_id", "tool_name", name="uq_config_tool"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # NOTE: column is tool_config (NOT config) to avoid SQLAlchemy relationship name conflict
    tool_config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    agent_config: Mapped["AgentConfig"] = relationship(back_populates="tools")

    def __repr__(self):
        return f"<AgentConfigTool(tool_name={self.tool_name}, enabled={self.enabled})>"


class AgentConfigMCP(Base):
    """
    Association table for AgentConfig -> MCP servers.

    Links a config to MCP servers for tool loading.
    Unique constraint ensures no duplicate MCP links per config.

    Phase 4: Enables per-config MCP server selection.
    """

    __tablename__ = "agent_config_mcp_servers"
    __table_args__ = (
        UniqueConstraint("config_id", "mcp_server_id", name="uq_config_mcp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    mcp_server_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_config: Mapped["AgentConfig"] = relationship(back_populates="mcp_links")
    mcp_server: Mapped["AgentMCPServer"] = relationship()

    def __repr__(self):
        return f"<AgentConfigMCP(mcp_server_id={self.mcp_server_id})>"


class AgentConfigKB(Base):
    """
    Association table for AgentConfig -> knowledge bases.

    Links a config to knowledge bases for RAG retrieval.
    Unique constraint ensures no duplicate KB links per config.
    Stores per-KB config like top_k, rank_threshold.

    Phase 4: Enables per-config KB selection.
    """

    __tablename__ = "agent_config_kbs"
    __table_args__ = (UniqueConstraint("config_id", "kb_id", name="uq_config_kb"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kb_config: Mapped[dict] = mapped_column(JSON, default=dict)  # top_k, threshold

    agent_config: Mapped["AgentConfig"] = relationship(back_populates="kb_links")

    def __repr__(self):
        return f"<AgentConfigKB(kb_id={self.kb_id})>"
