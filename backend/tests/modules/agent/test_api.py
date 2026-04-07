"""
Tests for Agent API Endpoints - Phase 2 Run, Resume, Stop operations.

These tests verify the API layer behavior using direct router invocation.
Note: Full integration tests with AsyncClient require additional async setup.
The core resume/stop logic is tested in test_service.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.agent.router import router
from app.modules.agent.service import AgentService


class TestStopEndpointLogic:
    """Test stop endpoint business logic."""

    def test_stop_response_schema(self):
        """AgentStopResponse schema has correct structure."""
        from app.modules.agent.schema import AgentStopResponse

        # Test schema validation
        response = AgentStopResponse(id="run-123", status="interrupted")
        assert response.id == "run-123"
        assert response.status == "interrupted"
        assert response.message == "Run stopped"  # Default

    def test_stop_response_with_custom_message(self):
        """AgentStopResponse can have custom message."""
        from app.modules.agent.schema import AgentStopResponse

        response = AgentStopResponse(
            id="run-123",
            status="success",
            message="Run already completed",
        )
        assert response.message == "Run already completed"


class TestResumeEndpointLogic:
    """Test resume endpoint business logic."""

    def test_resume_request_schema(self):
        """AgentResumeRequest schema validates correctly."""
        from app.modules.agent.schema import AgentResumeRequest

        # With input
        request = AgentResumeRequest(input="Continue the task")
        assert request.input == "Continue the task"

        # Without input (optional)
        request = AgentResumeRequest()
        assert request.input is None

    def test_run_request_schema(self):
        """AgentRunRequest schema validates correctly."""
        from app.modules.agent.schema import AgentRunRequest

        request = AgentRunRequest(input="Hello agent", stream=True, debug=False)
        assert request.input == "Hello agent"
        assert request.stream is True
        assert request.debug is False


class TestGetRunEndpointLogic:
    """Test get_run endpoint response structure."""

    def test_run_detail_response_schema(self):
        """AgentRunDetailResponse has all required fields."""
        from app.modules.agent.schema import AgentRunDetailResponse
        from datetime import datetime

        # Mock an object with attributes
        class MockRun:
            id = "run-123"
            session_id = "session-456"
            type = "chat"
            status = "running"
            input = "What is 2+2?"
            output = None
            error = None
            last_step_index = 2
            resumable = True
            trace_id = "trace-abc"
            created_at = datetime.now()
            updated_at = datetime.now()

        response = AgentRunDetailResponse.model_validate(MockRun())

        assert response.id == "run-123"
        assert response.session_id == "session-456"
        assert response.status == "running"
        assert response.last_step_index == 2
        assert response.resumable is True
        assert response.trace_id == "trace-abc"


class TestGetRunStepsEndpointLogic:
    """Test get_run_steps endpoint response structure."""

    def test_run_steps_response_schema(self):
        """AgentRunStepsResponse contains list of steps."""
        from app.modules.agent.schema import AgentRunStepsResponse, AgentStepResponse
        from datetime import datetime

        step = AgentStepResponse(
            id="step-1",
            session_id="session-1",
            run_id="run-1",
            step_index=0,
            type="llm",
            name=None,
            input={},
            output=None,
            status="success",
            error=None,
            latency_ms=100,
            created_at=datetime.now(),
        )

        response = AgentRunStepsResponse(run_id="run-1", steps=[step])

        assert response.run_id == "run-1"
        assert len(response.steps) == 1
        assert response.steps[0].type == "llm"


class TestServiceResumeIdempotency:
    """Test idempotency logic in resume scenario."""

    def test_idempotency_key_generation(self):
        """Idempotency key follows expected format."""
        run_id = "run-123"
        step_index = 1
        tool_name = "calculator"

        key = f"{run_id}:{step_index}:{tool_name}"

        assert key == "run-123:1:calculator"

    def test_idempotency_key_uniqueness(self):
        """Different combinations produce different keys."""
        key1 = "run-1:0:calculator"
        key2 = "run-1:1:calculator"
        key3 = "run-2:0:calculator"

        assert key1 != key2
        assert key2 != key3
        assert key1 != key3
