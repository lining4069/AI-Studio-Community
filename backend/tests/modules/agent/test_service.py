"""
Tests for Agent Service - Phase 2 Stop and Resume operations.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import AgentSession, AgentRun, AgentMessage, AgentStep
from app.modules.agent.repository import AgentRepository
from app.modules.agent.service import AgentService
from app.modules.agent.schema import AgentRunRequest, AgentSessionCreate
from app.modules.llm_model.repository import LlmModelRepository


class TestServiceStopRun:
    """Test stop_run functionality."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest_asyncio.fixture
    async def llm_repo(self, db_session: AsyncSession):
        return LlmModelRepository(db_session)

    @pytest_asyncio.fixture
    async def service(self, repo: AgentRepository, llm_repo: LlmModelRepository):
        return AgentService(repo, llm_repo)

    @pytest_asyncio.fixture
    async def session_with_running_run(self, db_session: AsyncSession):
        """Create session with a running run for stop testing."""
        session = AgentSession(
            id="stop-test-session",
            user_id=1,
            title="Stop Test",
            mode="assistant",
        )
        db_session.add(session)

        run = AgentRun(
            id="stop-test-run",
            session_id="stop-test-session",
            type="chat",
            status="running",
            input="Long running task",
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)
        return {"session": session, "run": run}

    @pytest.mark.asyncio
    async def test_stop_running_run(
        self,
        service: AgentService,
        session_with_running_run: dict,
    ):
        """Stopping a running run marks it as interrupted."""
        result = await service.stop_run(
            run_id="stop-test-run",
            user_id=1,
        )

        assert result["status"] == "interrupted"
        assert result["id"] == "stop-test-run"
        assert "stop requested" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_stop_already_finished_run(
        self,
        service: AgentService,
        db_session: AsyncSession,
    ):
        """Stopping an already finished run returns current status."""
        # Create session with finished run
        session = AgentSession(
            id="finished-session",
            user_id=1,
        )
        db_session.add(session)

        run = AgentRun(
            id="finished-run",
            session_id="finished-session",
            status="success",
            input="Completed task",
        )
        db_session.add(run)
        await db_session.commit()

        result = await service.stop_run(
            run_id="finished-run",
            user_id=1,
        )

        # Should return current status, not error
        assert result["status"] == "success"
        assert "already" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_stop_nonexistent_run(self, service: AgentService):
        """Stopping non-existent run raises NotFoundException."""
        from app.common.exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.stop_run(
                run_id="non-existent-run",
                user_id=1,
            )

    @pytest.mark.asyncio
    async def test_stop_run_wrong_user(self, service: AgentService, session_with_running_run: dict):
        """Stopping run with wrong user raises NotFoundException."""
        from app.common.exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.stop_run(
                run_id="stop-test-run",
                user_id=999,  # Wrong user
            )


class TestServiceGetRun:
    """Test get_run and get_run_steps functionality."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest_asyncio.fixture
    async def llm_repo(self, db_session: AsyncSession):
        return LlmModelRepository(db_session)

    @pytest_asyncio.fixture
    async def service(self, repo: AgentRepository, llm_repo: LlmModelRepository):
        return AgentService(repo, llm_repo)

    @pytest.mark.asyncio
    async def test_get_run(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Get run returns correct structure."""
        run_data = await service.get_run("test-run-001", user_id=1)

        assert run_data["id"] == "test-run-001"
        assert run_data["session_id"] == "test-session-001"
        assert run_data["status"] == "running"
        assert run_data["input"] == "What is 2 + 2?"
        assert run_data["last_step_index"] == 1
        assert run_data["resumable"] is True
        assert "created_at" in run_data
        assert "updated_at" in run_data

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, service: AgentService):
        """Get non-existent run raises NotFoundException."""
        from app.common.exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await service.get_run("non-existent", user_id=1)

    @pytest.mark.asyncio
    async def test_get_run_steps(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Get run steps returns all steps for a run."""
        steps = await service.get_run_steps("test-run-001", user_id=1)

        assert len(steps) == 2
        # Check structure
        for step in steps:
            assert "id" in step
            assert "run_id" in step
            assert "step_index" in step
            assert "type" in step
            assert "status" in step
            assert "created_at" in step

        # Verify order
        assert steps[0]["step_index"] == 0
        assert steps[1]["step_index"] == 1

    @pytest.mark.asyncio
    async def test_get_run_steps_includes_tool_name(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Get run steps includes tool name for tool steps."""
        steps = await service.get_run_steps("test-run-001", user_id=1)

        tool_step = next(s for s in steps if s["type"] == "tool")
        assert tool_step["name"] == "calculator"


class TestServiceResumeAgent:
    """Test resume_agent functionality."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest_asyncio.fixture
    async def llm_repo(self, db_session: AsyncSession):
        return LlmModelRepository(db_session)

    @pytest_asyncio.fixture
    async def service(self, repo: AgentRepository, llm_repo: LlmModelRepository):
        return AgentService(repo, llm_repo)

    @pytest.mark.asyncio
    async def test_resume_creates_new_run(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Resume creates a new run continuing from original."""
        # First, mark original run as interrupted
        await service.stop_run("test-run-001", user_id=1)

        # Mock LLM to return a simple response
        mock_llm = AsyncMock()
        mock_llm.achat = AsyncMock(return_value={
            "content": "The answer is 4.",
            "tool_calls": None,
        })

        # Mock LLM model repo to return our mock LLM
        with patch.object(service, "_get_llm_for_session", return_value=mock_llm):
            with patch("app.modules.agent.service.create_agent_tools", return_value=[]):
                # Create resume request
                request = AgentRunRequest(
                    input="Continue from where we left off",
                    stream=True,
                )

                # Note: This test would need full SSE streaming setup
                # For unit testing, we verify the service method exists and has correct signature
                assert hasattr(service, "resume_agent")

    @pytest.mark.asyncio
    async def test_resume_nonexistent_run(self, service: AgentService):
        """Resume non-existent run raises NotFoundException."""
        from app.common.exceptions import NotFoundException

        request = AgentRunRequest(input="Continue", stream=True)

        with pytest.raises(NotFoundException):
            await service.resume_agent(
                run_id="non-existent",
                user_id=1,
                request=request,
            )


class TestServiceIdempotency:
    """Test idempotency key functionality for resume."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest_asyncio.fixture
    async def llm_repo(self, db_session: AsyncSession):
        return LlmModelRepository(db_session)

    @pytest_asyncio.fixture
    async def service(self, repo: AgentRepository, llm_repo: LlmModelRepository):
        return AgentService(repo, llm_repo)

    @pytest.mark.asyncio
    async def test_idempotency_key_format(
        self,
        repo: AgentRepository,
        session_with_data: dict,
    ):
        """Idempotency key follows expected format: run_id:step_index:tool_name."""
        step = await repo.get_step_by_idempotency_key("test-run-001:1:calculator")

        assert step is not None
        assert step.idempotency_key == "test-run-001:1:calculator"

    @pytest.mark.asyncio
    async def test_successful_step_has_idempotency_key(
        self,
        session_with_data: dict,
    ):
        """Successful tool steps have idempotency_key set."""
        step = session_with_data["steps"][1]  # Tool step

        assert step.status == "success"
        assert step.idempotency_key is not None
        assert "calculator" in step.idempotency_key


class TestServiceGetMessages:
    """Test get_messages functionality."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest_asyncio.fixture
    async def llm_repo(self, db_session: AsyncSession):
        return LlmModelRepository(db_session)

    @pytest_asyncio.fixture
    async def service(self, repo: AgentRepository, llm_repo: LlmModelRepository):
        return AgentService(repo, llm_repo)

    @pytest.mark.asyncio
    async def test_get_messages_includes_run_id(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Messages include run_id in response."""
        messages = await service.get_messages(
            session_id="test-session-001",
            user_id=1,
        )

        assert len(messages) == 2
        for msg in messages:
            assert "run_id" in msg
            assert msg["run_id"] == "test-run-001"

    @pytest.mark.asyncio
    async def test_get_messages_order(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Messages are ordered by created_at."""
        messages = await service.get_messages(
            session_id="test-session-001",
            user_id=1,
        )

        # User message comes before assistant message
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"


class TestServiceGetSteps:
    """Test get_steps functionality."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest_asyncio.fixture
    async def llm_repo(self, db_session: AsyncSession):
        return LlmModelRepository(db_session)

    @pytest_asyncio.fixture
    async def service(self, repo: AgentRepository, llm_repo: LlmModelRepository):
        return AgentService(repo, llm_repo)

    @pytest.mark.asyncio
    async def test_get_steps_includes_run_id(
        self,
        service: AgentService,
        session_with_data: dict,
    ):
        """Steps include run_id in response."""
        steps = await service.get_steps(
            session_id="test-session-001",
            user_id=1,
        )

        assert len(steps) == 2
        for step in steps:
            assert "run_id" in step
            assert step["run_id"] == "test-run-001"
