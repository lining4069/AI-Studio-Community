"""
Tests for Agent Core - Step, AgentState, AgentEvent data structures.

Validates data models used throughout the agent system.
"""

import time

from app.services.agent.core import (
    AgentEvent,
    AgentEventType,
    AgentState,
    Step,
    StepType,
)


class TestStep:
    """Test Step data structure."""

    def test_step_creation(self):
        """Test step can be created with required fields."""
        step = Step(
            type=StepType.LLM_DECISION,
            name="openai",
        )

        assert step.type == StepType.LLM_DECISION
        assert step.name == "openai"
        assert step.step_index is None  # Assigned when added to AgentState
        assert step.id is None  # Set by DB on persistence

    def test_step_with_all_fields(self):
        """Test step creation with all fields."""
        step = Step(
            type=StepType.TOOL,
            name="calculator",
            step_index=1,
            input={"expression": "2+2"},
            output={"result": 4},
            status="success",
            latency_ms=100,
            error=None,
            role="tool",
        )

        assert step.type == StepType.TOOL
        assert step.name == "calculator"
        assert step.step_index == 1
        assert step.input == {"expression": "2+2"}
        assert step.output == {"result": 4}
        assert step.status == "success"
        assert step.latency_ms == 100

    def test_step_to_dict(self):
        """Test step converts to dict correctly."""
        step = Step(
            type=StepType.LLM_RESPONSE,
            name="openai",
            input={"messages": []},
            output={"content": "Hello!"},
            status="success",
        )

        step_dict = step.to_dict()

        assert step_dict["type"] == "llm_response"
        assert step_dict["name"] == "openai"
        assert step_dict["status"] == "success"
        assert "id" in step_dict
        assert "step_index" in step_dict

    def test_step_timing_fields(self):
        """Test timing fields are set correctly."""
        start = time.time()
        step = Step(
            type=StepType.LLM_DECISION,
            name="test",
        )
        step.status = "success"
        step.latency_ms = 50

        assert step.latency_ms == 50
        # created_at is not part of Step dataclass - it's set by DB on persistence


class TestAgentState:
    """Test AgentState data structure."""

    def test_agent_state_creation(self):
        """Test agent state can be created."""
        state = AgentState(
            session_id="session-123",
            user_input="Hello!",
        )

        assert state.session_id == "session-123"
        assert state.user_input == "Hello!"
        assert state.output is None
        assert state.finished is False
        assert state.steps == []
        assert state.messages == []
        assert state.tool_results == {}

    def test_agent_state_with_history(self):
        """Test agent state with message history."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

        state = AgentState(
            session_id="session-123",
            user_input="How are you?",
            messages=messages,
        )

        assert len(state.messages) == 2
        assert state.messages[0]["content"] == "Hi"

    def test_agent_state_add_step(self):
        """Test adding steps to state."""
        state = AgentState(
            session_id="session-123",
            user_input="Test",
        )

        step1 = Step(type=StepType.LLM_DECISION, name="llm")
        step2 = Step(type=StepType.TOOL, name="calc")

        state.add_step(step1)
        state.add_step(step2)

        assert len(state.steps) == 2
        assert state.steps[0].type == StepType.LLM_DECISION
        assert state.steps[1].type == StepType.TOOL
        # step_index is assigned by add_step
        assert state.steps[0].step_index == 0
        assert state.steps[1].step_index == 1

    def test_agent_state_finish(self):
        """Test finishing agent state."""
        state = AgentState(
            session_id="session-123",
            user_input="Test",
        )

        state.output = "Done!"
        state.finished = True

        assert state.output == "Done!"
        assert state.finished is True


class TestAgentEvent:
    """Test AgentEvent data structure."""

    def test_agent_event_creation(self):
        """Test agent event can be created."""
        event = AgentEvent(
            event=AgentEventType.STEP_START,
            data={"step_id": "step-1", "type": "llm"},
        )

        assert event.event == AgentEventType.STEP_START
        assert event.data["step_id"] == "step-1"

    def test_agent_event_with_run_id(self):
        """Test agent event includes run_id when provided."""
        event = AgentEvent(
            event=AgentEventType.STEP_END,
            data={"step_id": "step-1", "run_id": "run-123"},
        )

        assert event.data["run_id"] == "run-123"


class TestStepType:
    """Test StepType enum."""

    def test_step_types_exist(self):
        """Test all expected step types exist."""
        assert StepType.LLM_THOUGHT is not None
        assert StepType.LLM_DECISION is not None
        assert StepType.LLM_RESPONSE is not None
        assert StepType.LLM_OBSERVATION is not None
        assert StepType.TOOL is not None

    def test_step_type_values(self):
        """Test step type string values."""
        assert StepType.LLM_THOUGHT.value == "llm_thought"
        assert StepType.LLM_DECISION.value == "llm_decision"
        assert StepType.LLM_RESPONSE.value == "llm_response"
        assert StepType.LLM_OBSERVATION.value == "llm_observation"
        assert StepType.TOOL.value == "tool"


class TestAgentEventType:
    """Test AgentEventType enum."""

    def test_event_types_exist(self):
        """Test all expected event types exist."""
        assert AgentEventType.STEP_START is not None
        assert AgentEventType.STEP_END is not None
        assert AgentEventType.THOUGHT is not None
        assert AgentEventType.TOOL_CALL is not None
        assert AgentEventType.TOOL_RESULT is not None
        assert AgentEventType.OBSERVATION is not None
        assert AgentEventType.CONTENT is not None
        assert AgentEventType.RUN_END is not None
        assert AgentEventType.ERROR is not None

    def test_event_type_values(self):
        """Test event type string values."""
        assert AgentEventType.STEP_START.value == "step_start"
        assert AgentEventType.STEP_END.value == "step_end"
        assert AgentEventType.TOOL_CALL.value == "tool_call"
        assert AgentEventType.RUN_END.value == "run_end"
