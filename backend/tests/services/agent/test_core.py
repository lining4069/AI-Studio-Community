import pytest
import importlib.util
from dataclasses import asdict
from pathlib import Path

# Direct module load to avoid triggering app.services.__init__.py which has heavy imports
# that require settings environment variables
BASE = Path(__file__).parent.parent.parent.parent
_core_path = BASE / "app" / "services" / "agent" / "core.py"
_spec = importlib.util.spec_from_file_location("app.services.agent.core", _core_path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

Step = _core.Step
AgentState = _core.AgentState
AgentEvent = _core.AgentEvent


def test_step_creation():
    """Step can be created with type and defaults."""
    step = Step(type="llm", name="gpt-4o")
    assert step.type == "llm"
    assert step.name == "gpt-4o"
    assert step.status == "pending"
    assert step.input == {}
    assert step.output is None


def test_step_to_dict():
    """Step converts to dict for JSON serialization."""
    step = Step(type="tool", name="calculator", input={"expression": "2+2"})
    d = step.to_dict()
    assert d["type"] == "tool"
    assert d["name"] == "calculator"
    assert d["input"] == {"expression": "2+2"}


def test_agent_state_initialization():
    """AgentState initializes with empty messages and steps."""
    state = AgentState(session_id="sess-123", user_input="Hello")
    assert state.session_id == "sess-123"
    assert state.user_input == "Hello"
    assert state.messages == []
    assert state.steps == []


def test_agent_event_step_start():
    """AgentEvent can represent step_start event."""
    event = AgentEvent(
        event="step_start",
        data={"type": "llm", "name": "gpt-4o"}
    )
    assert event.event == "step_start"
    assert event.data["type"] == "llm"