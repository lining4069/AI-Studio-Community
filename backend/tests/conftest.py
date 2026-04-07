"""
Pytest configuration and shared fixtures for Agent tests.
"""

import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment before importing app modules
os.environ.setdefault("ENVIRONMENT", "test")

from app.common.base import Base
from app.modules.agent.models import AgentSession, AgentRun, AgentMessage, AgentStep


@pytest_asyncio.fixture
async def db_session():
    """
    Create an in-memory SQLite database session for testing.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def session_with_data(db_session: AsyncSession):
    """
    Create a session with test data (AgentSession, AgentRun, messages, steps).
    """
    # Create session
    session = AgentSession(
        id="test-session-001",
        user_id=1,
        title="Test Session",
        mode="assistant",
        summary="Previous conversation summary",
    )
    db_session.add(session)

    # Create run (running state)
    run = AgentRun(
        id="test-run-001",
        session_id="test-session-001",
        type="chat",
        status="running",
        input="What is 2 + 2?",
        trace_id="trace-001",
        last_step_index=1,
        resumable=True,
    )
    db_session.add(run)

    # Create user message
    user_msg = AgentMessage(
        id="test-msg-001",
        session_id="test-session-001",
        run_id="test-run-001",
        role="user",
        content="What is 2 + 2?",
    )
    db_session.add(user_msg)

    # Create assistant message
    assistant_msg = AgentMessage(
        id="test-msg-002",
        session_id="test-session-001",
        run_id="test-run-001",
        role="assistant",
        content="Let me calculate that.",
    )
    db_session.add(assistant_msg)

    # Create steps (step 0: LLM call, step 1: tool call)
    step1 = AgentStep(
        id="test-step-001",
        session_id="test-session-001",
        run_id="test-run-001",
        step_index=0,
        type="llm",
        status="success",
        output={"content": "I'll use the calculator.", "tool_call": "calculator"},
    )
    step2 = AgentStep(
        id="test-step-002",
        session_id="test-session-001",
        run_id="test-run-001",
        step_index=1,
        type="tool",
        name="calculator",
        status="success",
        input={"expression": "2 + 2"},
        output={"result": 4},
        idempotency_key="test-run-001:1:calculator",
    )
    db_session.add(step1)
    db_session.add(step2)

    await db_session.commit()
    await db_session.refresh(session)
    await db_session.refresh(run)

    return {
        "session": session,
        "run": run,
        "user_msg": user_msg,
        "assistant_msg": assistant_msg,
        "steps": [step1, step2],
    }


@pytest.fixture
def sample_run_data():
    """Sample run data for testing."""
    return {
        "session_id": "test-session-001",
        "input": "What is 2 + 2?",
        "type": "chat",
        "trace_id": "trace-001",
    }


@pytest.fixture
def sample_step_data():
    """Sample step data for testing."""
    return {
        "session_id": "test-session-001",
        "run_id": "test-run-001",
        "step_index": 0,
        "type": "llm",
        "status": "pending",
    }
