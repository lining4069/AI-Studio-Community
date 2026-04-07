"""
Agent core data structures: Step, AgentState, AgentEvent.

These are runtime state objects, NOT ORM models.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# =============================================================================
# Event Type Enum - Avoid hardcoded strings
# =============================================================================


class AgentEventType(StrEnum):
    """Agent SSE event types - must match SSE protocol."""

    STEP_START = "step_start"
    STEP_END = "step_end"
    CONTENT = "content"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_END = "run_end"
    ERROR = "error"


# =============================================================================
# Step - Minimal Execution Unit
# =============================================================================


@dataclass
class Step:
    """
    Represents a single execution step in the Agent loop.

    Attributes:
        id: Unique step ID (set by DB on persistence)
        type: Step type - "llm", "tool", or "retrieval"
        name: Name of the tool/model (optional for llm)
        input: Step input as dict
        output: Step output as dict (optional)
        status: Step status - "pending", "running", "success", "error"
        thought: ReAct thought text (optional, for future Phase 3)
        error: Error message if status is "error"
        latency_ms: Execution latency in milliseconds
        step_index: Order of this step in the session (set by AgentState.add_step)
    """

    type: str
    id: str | None = None  # DB-assigned on persistence
    name: str | None = None
    input: dict = field(default_factory=dict)
    output: dict | None = None
    status: str = "pending"
    thought: str | None = None
    error: str | None = None
    latency_ms: int | None = None
    step_index: int | None = None

    def to_dict(self) -> dict:
        """Convert step to dict for serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "thought": self.thought,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "step_index": self.step_index,
        }


# =============================================================================
# AgentState - Runtime State
# =============================================================================


@dataclass
class AgentState:
    """
    Runtime state for Agent execution.

    Holds messages, steps, scratchpad, and control flags.
    State is reconstructible from messages + steps (not stored as blob).
    """

    session_id: str
    user_input: str

    # Conversation
    messages: list[dict] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    # Scratchpad for intermediate results
    scratchpad: dict[str, Any] = field(default_factory=dict)

    # Tool results keyed by tool name
    tool_results: dict[str, Any] = field(default_factory=dict)

    # Control flags
    finished: bool = False
    output: str | None = None

    # Memory
    summary: str | None = None

    def add_step(self, step: Step) -> None:
        """Add a step to the execution trace."""
        step.step_index = len(self.steps)
        self.steps.append(step)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append({"role": role, "content": content})

    def to_result(self) -> dict:
        """Convert final state to result dict."""
        return {
            "session_id": self.session_id,
            "output": self.output,
            "finished": self.finished,
            "summary": self.summary,
            "steps": [s.to_dict() for s in self.steps],
        }


# =============================================================================
# AgentEvent - SSE Event
# =============================================================================


@dataclass
class AgentEvent:
    """
    SSE event for streaming responses.

    Represents a single event in the event stream.
    """

    event: AgentEventType
    data: dict

    def to_sse(self) -> str:
        """Convert to SSE format string."""
        # SSE "data" field should NOT include "event" type - it's in SSE protocol header
        return f"event: {self.event.value}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"
