import pytest
from app.modules.agent.models import AgentSession, AgentMessage, AgentStep


def test_agent_session_model():
    """AgentSession has correct fields."""
    assert hasattr(AgentSession, "id")
    assert hasattr(AgentSession, "user_id")
    assert hasattr(AgentSession, "title")
    assert hasattr(AgentSession, "mode")
    assert hasattr(AgentSession, "summary")


def test_agent_message_model():
    """AgentMessage has correct fields."""
    assert hasattr(AgentMessage, "id")
    assert hasattr(AgentMessage, "session_id")
    assert hasattr(AgentMessage, "role")
    assert hasattr(AgentMessage, "content")


def test_agent_step_model():
    """AgentStep has correct fields."""
    assert hasattr(AgentStep, "id")
    assert hasattr(AgentStep, "session_id")
    assert hasattr(AgentStep, "step_index")
    assert hasattr(AgentStep, "type")
    assert hasattr(AgentStep, "status")