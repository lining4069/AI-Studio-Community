"""
Tests for SimpleAgent - Phase 1 lightweight Agent with 1-loop execution.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
import importlib.util
import sys

# Load core module directly to avoid settings issues
from pathlib import Path
BASE = Path(__file__).parent.parent.parent.parent
_core_path = BASE / "app" / "services" / "agent" / "core.py"
_spec = importlib.util.spec_from_file_location("app.services.agent.core", _core_path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
sys.modules['app.services.agent.core'] = _core

AgentState = _core.AgentState
Step = _core.Step
AgentEvent = _core.AgentEvent

# Mock prompt_builder before loading simple_agent
_mock_pb = MagicMock()
sys.modules['app.services.agent.prompt_builder'] = _mock_pb
sys.modules['app.services.agent.prompt_builder'].build_messages = MagicMock()
sys.modules['app.services.agent.prompt_builder'].build_system_prompt = MagicMock()

# Mock LLMProvider before loading simple_agent
_mock_provider_base = MagicMock()
sys.modules['app.services.providers.base'] = _mock_provider_base
sys.modules['app.services.providers.base'].LLMProvider = MagicMock

# Mock loguru
sys.modules['loguru'] = MagicMock()
sys.modules['loguru'].logger = MagicMock()
sys.modules['loguru'].logger.error = MagicMock()

# Now load simple_agent directly
_simple_agent_path = BASE / "app" / "services" / "agent" / "simple_agent.py"
_spec = importlib.util.spec_from_file_location("app.services.agent.simple_agent", _simple_agent_path)
_simple_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_simple_agent)

SimpleAgent = _simple_agent.SimpleAgent


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name: str, description: str = "A mock tool"):
        self.name = name
        self.description = description
        self.schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def run(self, arguments: dict):
        return {"result": f"tool_{self.name}_executed", "args": arguments}


@pytest.mark.asyncio
async def test_simple_agent_direct_response():
    """SimpleAgent responds directly when no tool is needed."""
    # Setup mock LLM that returns a direct response
    mock_llm = AsyncMock()
    mock_llm.provider_name = "mock-llm"
    mock_llm.achat = AsyncMock(return_value={
        "content": "Hello! How can I help you?",
        "tool_calls": None,
    })

    # Create agent with no tools
    agent = SimpleAgent(
        llm=mock_llm,
        tools=[],
        max_loop=1,
    )

    # Create initial state
    state = AgentState(
        session_id="test-session-1",
        user_input="Hello!",
    )

    # Run agent
    result_state = await agent.run(state)

    # Verify LLM was called once
    assert mock_llm.achat.call_count == 1

    # Verify response
    assert result_state.output == "Hello! How can I help you?"
    assert result_state.finished is True
    assert len(result_state.steps) == 1
    assert result_state.steps[0].type == "llm"
    assert result_state.steps[0].status == "success"


@pytest.mark.asyncio
async def test_simple_agent_with_tool_call():
    """SimpleAgent calls tool and feeds result back to LLM."""
    # Setup mock tool
    mock_tool = MockTool(name="calculator", description="A calculator tool")

    # Setup mock LLM that first returns a tool call, then a final response
    mock_llm = AsyncMock()
    mock_llm.provider_name = "mock-llm"

    tool_call_response = {
        "content": "Let me calculate that for you.",
        "tool_calls": [{
            "id": "call_123",
            "function": {
                "name": "calculator",
                "arguments": {"expression": "2 + 2"},
            },
        }],
    }

    final_response = {
        "content": "The answer is 4.",
        "tool_calls": None,
    }

    mock_llm.achat = AsyncMock(side_effect=[tool_call_response, final_response])

    # Create agent with the mock tool
    agent = SimpleAgent(
        llm=mock_llm,
        tools=[mock_tool],
        max_loop=1,
    )

    # Create initial state
    state = AgentState(
        session_id="test-session-2",
        user_input="What is 2 + 2?",
    )

    # Run agent
    result_state = await agent.run(state)

    # Verify LLM was called twice (initial + after tool)
    assert mock_llm.achat.call_count == 2

    # Verify tool was recorded
    assert len(result_state.steps) == 3  # LLM (tool call) + Tool + LLM (final)
    assert result_state.steps[0].type == "llm"
    assert result_state.steps[0].output["tool_call"] == "calculator"
    assert result_state.steps[1].type == "tool"
    assert result_state.steps[1].name == "calculator"
    assert result_state.steps[2].type == "llm"

    # Verify final response
    assert result_state.output == "The answer is 4."
    assert result_state.finished is True

    # Verify tool result was stored
    assert "calculator" in result_state.tool_results
