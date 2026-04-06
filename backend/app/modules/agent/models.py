"""Agent system database models."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base, TimestampMixin


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


# ============================================================================
# Agent Session
# ============================================================================


class AgentSession(Base, TimestampMixin):
    """
    Agent conversation session.

    Represents a single conversation session with memory (summary).
    """

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Session configuration (for future use in Phase 2+)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default=AgentMode.ASSISTANT.value)

    # Light memory: conversation summary
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<AgentSession(id={self.id}, mode={self.mode})>"


# ============================================================================
# Agent Message
# ============================================================================


class AgentMessage(Base, TimestampMixin):
    """
    Agent conversation message.

    Stores user/assistant/system messages in a session.
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

    # Execution order (critical for replay)
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

    def __repr__(self):
        return f"<AgentStep(id={self.id}, type={self.type}, status={self.status})>"
