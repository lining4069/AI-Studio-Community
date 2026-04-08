"""
Agent core data structures: Step, AgentState, AgentEvent.

These are runtime state objects, NOT ORM models.

Phase 3 Ready Protocol:
- Step types: llm_decision, tool, llm_response
- Each STEP_START has exactly one STEP_END
- TOOL_CALL belongs to llm_decision step
- input/output structure is strictly defined
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
    THOUGHT = "thought"
    OBSERVATION = "observation"


# =============================================================================
# Step Type Enum - Phase 3 Ready
# =============================================================================


class StepType(StrEnum):
    """
    Step types for ReAct protocol.

    - llm_thought: LLM thinks about the problem
    - llm_decision: LLM decides to call a tool or respond
    - tool: Tool execution
    - llm_observation: LLM observes tool result
    - llm_response: LLM generates final response (no tool call)
    """

    LLM_THOUGHT = "llm_thought"
    LLM_DECISION = "llm_decision"
    TOOL = "tool"
    LLM_OBSERVATION = "llm_observation"
    LLM_RESPONSE = "llm_response"


# =============================================================================
# Step - Minimal Execution Unit
# =============================================================================


@dataclass
class Step:
    """
    Represents a single execution step in the Agent loop.

    Phase 3 Ready Protocol:
    - Each step has exactly one START and one END
    - llm_decision: input=messages+tools, output=decision
    - tool: input=arguments, output=result/error
    - llm_response: input=messages, output=content

    Attributes:
        id: Unique step ID (set by DB on persistence)
        type: Step type - "llm_decision", "tool", or "llm_response"
        role: Semantic role - "assistant" (for LLM steps) or "tool" (for tool steps)
        name: Name of the tool/model (optional)
        input: Step input (strictly defined per type)
        output: Step output (strictly defined per type)
        status: Step status - "pending", "running", "success", "error"
        error: Error message if status is "error"
        latency_ms: Execution latency in milliseconds
        step_index: Order of this step in the session (set by AgentState.add_step)
        trace: Optional debug info (raw prompts, responses, usage)
    """

    type: StepType | str
    role: str = "assistant"  # "assistant" for LLM, "tool" for tool
    id: str | None = None
    name: str | None = None
    input: dict = field(default_factory=dict)
    output: dict | None = None
    status: str = "pending"
    error: str | None = None
    latency_ms: int | None = None
    step_index: int | None = None
    trace: dict | None = None  # Debug info: raw prompts, responses, usage

    def to_dict(self) -> dict:
        """Convert step to dict for serialization."""
        return {
            "id": self.id,
            "type": str(self.type) if isinstance(self.type, StepType) else self.type,
            "role": self.role,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "step_index": self.step_index,
            "trace": self.trace,
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
