"""
Pytest configuration and shared fixtures for Agent System E2E tests.

Structure:
- conftest.py: Root fixtures (client, auth, db)
- e2e/: Full workflow tests
- unit/: Tool and core logic tests
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

# Set test environment before importing app modules
os.environ.setdefault("ENVIRONMENT", "test")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.common.base import Base
from app.main import app
from app.modules.agent.models import (
    AgentMessage,
    AgentRun,
    AgentSession,
    AgentStep,
)
from app.modules.agent.repository import AgentRepository
from app.modules.agent.service import AgentService
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.users.models import User  # noqa: F401 - needed for Base.metadata

# =============================================================================
# Test Settings
# =============================================================================

BASE_URL = "http://127.0.0.1:8000"
TEST_USER_ID = 1
TEST_TOKEN = "test-token-123"


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        # Enable foreign key constraints for SQLite
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def repo(db_session: AsyncSession) -> AgentRepository:
    """Create an AgentRepository instance."""
    return AgentRepository(db_session)


@pytest_asyncio.fixture
async def llm_repo(db_session: AsyncSession) -> LlmModelRepository:
    """Create an LLM model repository instance."""
    return LlmModelRepository(db_session)


@pytest_asyncio.fixture
async def service(repo: AgentRepository, llm_repo: LlmModelRepository) -> AgentService:
    """Create an AgentService instance."""
    return AgentService(repo, llm_repo)


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest.fixture
def auth_headers():
    """Return authorization headers for test requests."""
    return {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Content-Type": "application/json",
    }


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL, timeout=30.0) as c:
        yield c


# =============================================================================
# Mock LLM Fixtures
# =============================================================================

class MockLLMProvider:
    """
    Deterministic Mock LLM for testing.

    Allows registering expected prompts and their responses,
    making agent behavior predictable and testable.
    """

    def __init__(self):
        self.responses: dict[str, dict] = {}
        self.call_history: list[dict] = []

    def register(self, prompt_contains: str, response: dict):
        """
        Register a response for a prompt.

        Args:
            prompt_contains: Substring that should appear in the prompt
            response: Response dict with 'content' and optional 'tool_calls'
        """
        self.responses[prompt_contains] = response

    def register_tool_sequence(self, sequences: list[tuple[str, dict]]):
        """
        Register a sequence of responses for multi-step interactions.

        Args:
            sequences: List of (prompt_contains, response) tuples
        """
        for i, (prompt, response) in enumerate(sequences):
            self.responses[f"__seq_{i}__"] = {"_match": prompt, **response}

    async def achat(self, messages: list[dict], **kwargs) -> dict:
        """Async chat method for LLM provider interface."""
        last_msg = messages[-1]["content"] if messages else ""

        self.call_history.append({"messages": messages, "kwargs": kwargs})

        # Check sequence first
        for i in range(len(self.responses)):
            seq_key = f"__seq_{i}__"
            if seq_key in self.responses:
                match = self.responses[seq_key].get("_match", "")
                resp = {k: v for k, v in self.responses[seq_key].items() if k != "_match"}
                if match in last_msg:
                    return resp

        # Check substring matches
        for key, resp in self.responses.items():
            if key.startswith("__seq_"):
                continue
            if key in last_msg:
                return resp

        return {"content": "Mock response", "tool_calls": None}

    async def ainvoke(self, prompt: str, **kwargs) -> dict:
        """Async invoke method for simple prompts."""
        self.call_history.append({"prompt": prompt, "kwargs": kwargs})
        for key, resp in self.responses.items():
            if key in prompt:
                return {"content": resp.get("content", "")}
        return {"content": "Mock response"}


@pytest.fixture
def mock_llm():
    """Create a fresh MockLLMProvider for each test."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_calculator():
    """
    Pre-configured MockLLM for calculator tool testing.

    Returns:
        Tuple of (mock_llm, setup_fn) where setup_fn configures the mock
    """
    def setup(prompt: str = "计算", tool_expression: str = "1+2*3", final_answer: str = "7"):
        mock = MockLLMProvider()

        # First call: return tool call
        mock.register(
            prompt,
            {
                "content": f"我来计算 {tool_expression}",
                "tool_calls": [{
                    "id": "call_123",
                    "function": {
                        "name": "calculator",
                        "arguments": {"expression": tool_expression},
                    },
                }],
            },
        )

        # Second call: return final response
        mock.register(
            str({"result": float(final_answer)}),
            {"content": f"{tool_expression} = {final_answer}"},
        )

        return mock

    return setup


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_user_id():
    """Return test user ID."""
    return TEST_USER_ID


@pytest.fixture
async def session_with_data(db_session: AsyncSession, sample_user_id: int):
    """Create a session with test data (AgentSession, AgentRun, messages, steps)."""
    # Create session
    session = AgentSession(
        id="test-session-001",
        user_id=sample_user_id,
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

    # Create steps
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


# =============================================================================
# Snapshot Fixtures
# =============================================================================

class Snapshot:
    """
    Snapshot testing utility for verifying consistent results.

    Stores expected data on first run, then verifies consistency on subsequent runs.
    """

    def __init__(self, name: str, snapshot_dir: str = "tests/snapshots"):
        from pathlib import Path
        self.path = Path(snapshot_dir) / f"{name}.json"
        self._created = False

    def assert_match(self, data: dict) -> bool:
        """Assert that data matches the stored snapshot."""
        import json

        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            self._created = True
            pytest.fail(f"Snapshot created at {self.path}. Re-run test to verify.")

        expected = json.loads(self.path.read_text())
        if data != expected:
            # Write actual for comparison
            actual_path = self.path.with_suffix(".actual.json")
            actual_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            pytest.fail(f"Snapshot mismatch. Expected {self.path}, got {actual_path}")

        return True


@pytest.fixture
def snapshot(request):
    """Create a snapshot fixture for the current test."""
    return Snapshot(request.node.name)
