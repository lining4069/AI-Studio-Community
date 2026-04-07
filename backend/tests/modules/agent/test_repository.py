"""
Tests for Agent Repository - Phase 2 Run/Message/Step CRUD operations.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import AgentSession, AgentRun, AgentMessage, AgentStep
from app.modules.agent.repository import AgentRepository


class TestRepositoryRunOperations:
    """Test Run CRUD operations."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest.mark.asyncio
    async def test_create_run(self, repo: AgentRepository, sample_run_data: dict):
        """Run can be created and retrieved."""
        run = await repo.create_run(**sample_run_data)

        assert run.id is not None
        assert run.session_id == sample_run_data["session_id"]
        assert run.type == sample_run_data["type"]
        assert run.status == "running"  # Default status
        assert run.input == sample_run_data["input"]
        assert run.trace_id == sample_run_data["trace_id"]

    @pytest.mark.asyncio
    async def test_get_run(self, repo: AgentRepository, session_with_data: dict):
        """Run can be retrieved by ID with user ownership verification."""
        run = await repo.get_run("test-run-001", user_id=1)

        assert run is not None
        assert run.id == "test-run-001"
        assert run.status == "running"

    @pytest.mark.asyncio
    async def test_get_run_wrong_user(self, repo: AgentRepository, session_with_data: dict):
        """Run returns None for wrong user."""
        run = await repo.get_run("test-run-001", user_id=999)
        assert run is None

    @pytest.mark.asyncio
    async def test_get_run_no_user_check(self, repo: AgentRepository, session_with_data: dict):
        """Run can be retrieved without user check."""
        run = await repo.get_run("test-run-001", user_id=None)
        assert run is not None

    @pytest.mark.asyncio
    async def test_update_run(self, repo: AgentRepository, session_with_data: dict):
        """Run fields can be updated."""
        await repo.update_run(
            run_id="test-run-001",
            status="success",
            output="The answer is 4.",
            last_step_index=2,
        )

        run = await repo.get_run("test-run-001", user_id=None)
        assert run.status == "success"
        assert run.output == "The answer is 4."
        assert run.last_step_index == 2

    @pytest.mark.asyncio
    async def test_finish_run(self, repo: AgentRepository, session_with_data: dict):
        """finish_run marks run as finished."""
        await repo.finish_run(
            run_id="test-run-001",
            status="success",
            output="Final answer.",
        )

        run = await repo.get_run("test-run-001", user_id=None)
        assert run.status == "success"
        assert run.output == "Final answer."


class TestRepositoryMessageOperations:
    """Test Message CRUD operations."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest.mark.asyncio
    async def test_create_message(self, repo: AgentRepository, session_with_data: dict):
        """Message can be created with run_id."""
        msg = await repo.create_message(
            session_id="test-session-001",
            run_id="test-run-001",
            role="user",
            content="New message",
        )

        assert msg.id is not None
        assert msg.run_id == "test-run-001"
        assert msg.role == "user"
        assert msg.content == "New message"

    @pytest.mark.asyncio
    async def test_create_message_without_run_id(self, repo: AgentRepository, session_with_data: dict):
        """Message can be created without run_id (legacy)."""
        msg = await repo.create_message(
            session_id="test-session-001",
            role="system",
            content="System prompt",
        )

        assert msg.run_id is None
        assert msg.role == "system"

    @pytest.mark.asyncio
    async def test_get_messages_by_run_id(self, repo: AgentRepository, session_with_data: dict):
        """Messages can be filtered by run_id."""
        messages = await repo.get_messages(
            session_id="test-session-001",
            run_id="test-run-001",
        )

        assert len(messages) == 2  # user + assistant
        assert all(m.run_id == "test-run-001" for m in messages)

    @pytest.mark.asyncio
    async def test_get_messages_all(self, repo: AgentRepository, session_with_data: dict):
        """Messages can be retrieved without run_id filter."""
        messages = await repo.get_messages(session_id="test-session-001")

        assert len(messages) == 2


class TestRepositoryStepOperations:
    """Test Step CRUD operations."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest.mark.asyncio
    async def test_create_step(self, repo: AgentRepository, session_with_data: dict):
        """Step can be created with all fields."""
        step = await repo.create_step(
            session_id="test-session-001",
            run_id="test-run-001",
            step_index=2,
            type="tool",
            name="calculator",
            step_input={"expression": "3 + 3"},
            status="running",
            idempotency_key="test-run-001:2:calculator",
        )

        assert step.id is not None
        assert step.step_index == 2
        assert step.type == "tool"
        assert step.name == "calculator"
        assert step.status == "running"
        assert step.idempotency_key == "test-run-001:2:calculator"

    @pytest.mark.asyncio
    async def test_update_step(self, repo: AgentRepository, session_with_data: dict):
        """Step can be updated with output and status."""
        await repo.update_step(
            step_id="test-step-002",
            status="success",
            output={"result": 4},
            latency_ms=50,
        )

        step = await repo.get_step_by_idempotency_key("test-run-001:1:calculator")
        # get_step_by_idempotency_key returns the step
        # We need to query it differently
        from sqlalchemy import select
        from app.modules.agent.models import AgentStep
        result = await repo.db.execute(
            select(AgentStep).where(AgentStep.id == "test-step-002")
        )
        step = result.scalar_one()

        assert step.status == "success"
        assert step.output == {"result": 4}
        assert step.latency_ms == 50

    @pytest.mark.asyncio
    async def test_get_steps_by_run_id(self, repo: AgentRepository, session_with_data: dict):
        """Steps can be filtered by run_id."""
        steps = await repo.get_steps(
            session_id="test-session-001",
            run_id="test-run-001",
        )

        assert len(steps) == 2
        assert all(s.run_id == "test-run-001" for s in steps)
        # Ordered by step_index
        assert steps[0].step_index == 0
        assert steps[1].step_index == 1

    @pytest.mark.asyncio
    async def test_get_step_by_idempotency_key(self, repo: AgentRepository, session_with_data: dict):
        """Step can be found by idempotency_key."""
        step = await repo.get_step_by_idempotency_key("test-run-001:1:calculator")

        assert step is not None
        assert step.name == "calculator"
        assert step.status == "success"

    @pytest.mark.asyncio
    async def test_get_step_by_idempotency_key_not_found(self, repo: AgentRepository, session_with_data: dict):
        """Returns None for non-existent idempotency_key."""
        step = await repo.get_step_by_idempotency_key("non-existent-key")
        assert step is None


class TestRepositorySessionOperations:
    """Test Session operations."""

    @pytest_asyncio.fixture
    async def repo(self, db_session: AsyncSession):
        return AgentRepository(db_session)

    @pytest.mark.asyncio
    async def test_update_summary(self, repo: AgentRepository, session_with_data: dict):
        """Session summary can be updated."""
        await repo.update_summary("test-session-001", "New conversation summary")

        session = await repo.get_session("test-session-001", user_id=1)
        assert session.summary == "New conversation summary"
