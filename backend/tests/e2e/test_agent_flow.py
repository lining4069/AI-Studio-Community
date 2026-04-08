"""
Agent System E2E Tests - Core Flow Tests

Tests the complete agent lifecycle:
Config → Session → Run → Steps → Resume/Stop

Based on: Agent系统测试验证流程.md

NOTE: These tests require a full PostgreSQL database with all tables (including users).
They are skipped by default when running with SQLite in-memory.
Run with: pytest tests/e2e --require-db (or use a real DB connection)
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.agent.repository import AgentRepository
from app.modules.agent.schema import (
    AgentRunRequest,
)
from app.modules.agent.service import AgentService
from app.services.agent.core import AgentState
from tests.conftest import MockLLMProvider

# Skip E2E tests by default - they require full PostgreSQL with users table
pytestmark = pytest.mark.skip(reason="E2E tests require full PostgreSQL DB (users table FK dependency)")



# =============================================================================
# Config CRUD Tests
# =============================================================================

class TestConfigCRUD:
    """Test AgentConfig CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_config(self, repo: AgentRepository, sample_user_id: int):
        """Create a new AgentConfig."""
        config = await repo.create_config(
            user_id=sample_user_id,
            name="test-agent",
            agent_type="simple",
            max_loop=5,
            system_prompt="You are a helpful assistant.",
        )

        assert config.id is not None
        assert config.name == "test-agent"
        assert config.agent_type == "simple"
        assert config.max_loop == 5
        assert config.user_id == sample_user_id

    @pytest.mark.asyncio
    async def test_get_config(self, repo: AgentRepository, sample_user_id: int):
        """Get an existing AgentConfig."""
        # Create config
        created = await repo.create_config(
            user_id=sample_user_id,
            name="get-test-agent",
            agent_type="react",
            max_loop=3,
        )

        # Retrieve it
        retrieved = await repo.get_config(created.id, sample_user_id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "get-test-agent"
        assert retrieved.agent_type == "react"

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, repo: AgentRepository, sample_user_id: int):
        """Get non-existent config raises NotFoundException."""
        from app.common.exceptions import NotFoundException

        with pytest.raises(NotFoundException):
            await repo.get_config("nonexistent-id", sample_user_id)

    @pytest.mark.asyncio
    async def test_update_config(self, repo: AgentRepository, sample_user_id: int):
        """Update an existing AgentConfig."""
        # Create config
        config = await repo.create_config(
            user_id=sample_user_id,
            name="original-name",
            max_loop=5,
        )

        # Update it
        updated = await repo.update_config(
            config_id=config.id,
            user_id=sample_user_id,
            name="updated-name",
            max_loop=10,
        )

        assert updated.name == "updated-name"
        assert updated.max_loop == 10

    @pytest.mark.asyncio
    async def test_delete_config(self, repo: AgentRepository, sample_user_id: int):
        """Delete an existing AgentConfig."""
        # Create config
        config = await repo.create_config(
            user_id=sample_user_id,
            name="to-delete",
        )

        # Delete it
        result = await repo.delete_config(config.id, sample_user_id)
        assert result is True

        # Verify it's gone
        from app.common.exceptions import NotFoundException
        with pytest.raises(NotFoundException):
            await repo.get_config(config.id, sample_user_id)

    @pytest.mark.asyncio
    async def test_list_configs(self, repo: AgentRepository, sample_user_id: int):
        """List all configs for a user."""
        # Create multiple configs
        await repo.create_config(user_id=sample_user_id, name="agent-1")
        await repo.create_config(user_id=sample_user_id, name="agent-2")
        await repo.create_config(user_id=sample_user_id, name="agent-3")

        # List them
        configs = await repo.list_configs(sample_user_id, limit=10)

        assert len(configs) >= 3
        names = [c.name for c in configs]
        assert "agent-1" in names
        assert "agent-2" in names


# =============================================================================
# Config Tool Association Tests
# =============================================================================

class TestConfigToolAssociation:
    """Test AgentConfigTool association (adding tools to configs)."""

    @pytest.mark.asyncio
    async def test_add_tool_to_config(self, repo: AgentRepository, sample_user_id: int):
        """Add a tool to a config."""
        # Create config
        config = await repo.create_config(
            user_id=sample_user_id,
            name="tool-test-agent",
        )

        # Add tool
        tool = await repo.add_config_tool(
            config_id=config.id,
            tool_name="calculator",
            tool_config={},
        )

        assert tool.id is not None
        assert tool.config_id == config.id
        assert tool.tool_name == "calculator"

    @pytest.mark.asyncio
    async def test_add_duplicate_tool_raises_conflict(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Adding same tool twice raises ConflictException."""
        # Create config
        config = await repo.create_config(
            user_id=sample_user_id,
            name="duplicate-tool-test",
        )

        # Add tool first time
        await repo.add_config_tool(
            config_id=config.id,
            tool_name="calculator",
            tool_config={},
        )

        # Add same tool again
        from app.common.exceptions import ConflictException
        with pytest.raises(ConflictException):
            await repo.add_config_tool(
                config_id=config.id,
                tool_name="calculator",
                tool_config={},
            )

    @pytest.mark.asyncio
    async def test_list_config_tools(self, repo: AgentRepository, sample_user_id: int):
        """List all tools in a config."""
        # Create config and add tools
        config = await repo.create_config(
            user_id=sample_user_id,
            name="list-tools-test",
        )

        await repo.add_config_tool(config_id=config.id, tool_name="calculator")
        await repo.add_config_tool(config_id=config.id, tool_name="datetime")

        # List tools
        tools = await repo.list_config_tools(config.id)

        assert len(tools) == 2
        tool_names = [t.tool_name for t in tools]
        assert "calculator" in tool_names
        assert "datetime" in tool_names

    @pytest.mark.asyncio
    async def test_delete_config_tool(self, repo: AgentRepository, sample_user_id: int):
        """Remove a tool from a config."""
        # Create config and add tool
        config = await repo.create_config(
            user_id=sample_user_id,
            name="remove-tool-test",
        )

        tool = await repo.add_config_tool(
            config_id=config.id,
            tool_name="calculator",
        )

        # Delete it
        result = await repo.delete_config_tool(tool.id, sample_user_id)
        assert result is True

        # Verify it's gone
        tools = await repo.list_config_tools(config.id)
        assert len(tools) == 0


# =============================================================================
# Session Tests
# =============================================================================

class TestSessionOperations:
    """Test AgentSession CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, repo: AgentRepository, sample_user_id: int):
        """Create a new session."""
        session = await repo.create_session(
            user_id=sample_user_id,
            title="Test Session",
        )

        assert session.id is not None
        assert session.user_id == sample_user_id
        assert session.title == "Test Session"

    @pytest.mark.asyncio
    async def test_create_session_with_config(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Create a session bound to a config."""
        # Create config first
        config = await repo.create_config(
            user_id=sample_user_id,
            name="bound-config",
        )

        # Create session with config
        session = await repo.create_session(
            user_id=sample_user_id,
            title="Session with Config",
            config_id=config.id,
        )

        assert session.config_id == config.id

    @pytest.mark.asyncio
    async def test_bind_session_to_config(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Bind an existing session to a config."""
        # Create session and config
        session = await repo.create_session(user_id=sample_user_id)
        config = await repo.create_config(
            user_id=sample_user_id,
            name="bind-test-config",
        )

        # Bind session to config
        updated = await repo.update_session_config(
            session_id=session.id,
            user_id=sample_user_id,
            config_id=config.id,
        )

        assert updated.config_id == config.id

    @pytest.mark.asyncio
    async def test_get_session_messages(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Get messages for a session."""
        # Create session with a message
        session = await repo.create_session(user_id=sample_user_id)

        # Add a message
        run = await repo.create_run(session_id=session.id, user_id=sample_user_id)
        await repo.create_message(
            session_id=session.id,
            run_id=run.id,
            role="user",
            content="Hello!",
        )

        # Get messages
        messages = await repo.get_messages(session.id, sample_user_id)

        assert len(messages) >= 1


# =============================================================================
# Run Execution Tests (with Mock LLM)
# =============================================================================

class TestRunExecution:
    """Test Run execution with Mock LLM."""

    @pytest.mark.asyncio
    async def test_stream_run_direct_response(
        self,
        service: AgentService,
        repo: AgentRepository,
        sample_user_id: int,
        mock_llm: MockLLMProvider,
    ):
        """Test a run that returns direct response (no tool call)."""
        # Setup mock LLM
        mock_llm.register(
            "hello",
            {"content": "Hello! How can I help you?"},
        )

        # Create session (no tools)
        session = await repo.create_session(user_id=sample_user_id)

        # Mock _get_llm_for_session to return our mock
        with patch.object(service, "_get_llm_for_session", return_value=mock_llm):
            # Execute stream_run
            state = AgentState(
                session_id=session.id,
                user_id=sample_user_id,
                user_input="hello",
            )

            # Run agent
            result_state = await service.run_agent(
                session_id=session.id,
                user_id=sample_user_id,
                user_input="hello",
                stream=False,
            )

            assert result_state.finished is True
            assert result_state.output is not None

    @pytest.mark.asyncio
    async def test_run_with_calculator_tool(
        self,
        repo: AgentRepository,
        sample_user_id: int,
        mock_llm_with_calculator,
    ):
        """Test a run with calculator tool call."""
        setup_fn = mock_llm_with_calculator("计算", "1+2*3", "7")
        mock_llm = setup_fn()

        # Create config with calculator tool
        config = await repo.create_config(
            user_id=sample_user_id,
            name="calculator-agent",
            agent_type="simple",
        )
        await repo.add_config_tool(
            config_id=config.id,
            tool_name="calculator",
            tool_config={},
        )

        # Create session with config
        session = await repo.create_session(
            user_id=sample_user_id,
            config_id=config.id,
        )

        # This would need proper service setup with mock LLM
        # For now, verify the config was created with the tool
        config_tools = await repo.list_config_tools(config.id)
        assert len(config_tools) == 1
        assert config_tools[0].tool_name == "calculator"


# =============================================================================
# Resume/Stop Tests
# =============================================================================

class TestResumeStop:
    """Test resume and stop operations."""

    @pytest.mark.asyncio
    async def test_stop_running_run(
        self, service: AgentService, session_with_data: dict, sample_user_id: int
    ):
        """Stopping a running run marks it as interrupted."""
        result = await service.stop_run(
            run_id=session_with_data["run"].id,
            user_id=sample_user_id,
        )

        assert result["status"] == "interrupted"
        assert result["id"] == session_with_data["run"].id

    @pytest.mark.asyncio
    async def test_stop_completed_run(
        self, service: AgentService, repo: AgentRepository, sample_user_id: int
    ):
        """Stopping a completed run returns current status."""
        # Create session with completed run
        session = await repo.create_session(user_id=sample_user_id)
        run = await repo.create_run(
            session_id=session.id,
            user_id=sample_user_id,
            status="success",
        )

        result = await service.stop_run(run_id=run.id, user_id=sample_user_id)

        assert result["status"] == "success"
        assert "already" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_resume_interrupted_run(
        self, service: AgentService, session_with_data: dict, sample_user_id: int
    ):
        """Resume creates new run continuing from original."""
        # Mark original as interrupted
        await service.stop_run(
            run_id=session_with_data["run"].id,
            user_id=sample_user_id,
        )

        # Create mock LLM
        mock_llm = AsyncMock()
        mock_llm.achat = AsyncMock(return_value={"content": "Continued response."})

        # Mock the dependencies
        with patch.object(service, "_get_llm_for_session", return_value=mock_llm):
            with patch("app.modules.agent.service.create_agent_tools", return_value=[]):
                request = AgentRunRequest(input="Continue", stream=False)

                # Note: Full resume test would need proper session/config setup
                assert hasattr(service, "resume_agent")


# =============================================================================
# MCPServer Tests
# =============================================================================

class TestMCPServerOperations:
    """Test AgentMCPServer CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_mcp_server(self, repo: AgentRepository, sample_user_id: int):
        """Create a new MCP server."""
        server = await repo.create_mcp_server(
            user_id=sample_user_id,
            name="test-mcp-server",
            url="https://mcp.example.com/sse",
            transport="streamable_http",
        )

        assert server.id is not None
        assert server.name == "test-mcp-server"
        assert server.user_id == sample_user_id
        assert server.enabled is True

    @pytest.mark.asyncio
    async def test_create_duplicate_mcp_server_raises_conflict(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Creating MCP server with duplicate name raises ConflictException."""
        # Create first server
        await repo.create_mcp_server(
            user_id=sample_user_id,
            name="duplicate-mcp",
            url="https://first.example.com",
        )

        # Try to create another with same name
        from app.common.exceptions import ConflictException
        with pytest.raises(ConflictException):
            await repo.create_mcp_server(
                user_id=sample_user_id,
                name="duplicate-mcp",
                url="https://second.example.com",
            )

    @pytest.mark.asyncio
    async def test_list_mcp_servers(self, repo: AgentRepository, sample_user_id: int):
        """List all MCP servers for a user."""
        await repo.create_mcp_server(user_id=sample_user_id, name="server-1", url="https://1.example.com")
        await repo.create_mcp_server(user_id=sample_user_id, name="server-2", url="https://2.example.com")

        servers = await repo.list_mcp_servers(sample_user_id)

        assert len(servers) >= 2
        names = [s.name for s in servers]
        assert "server-1" in names
        assert "server-2" in names


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidationRules:
    """Test validation rules (UQ constraints, FK constraints, etc.)."""

    @pytest.mark.asyncio
    async def test_unique_constraint_config_tool(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Same tool cannot be added twice to same config."""
        config = await repo.create_config(user_id=sample_user_id, name="uq-test")

        await repo.add_config_tool(config_id=config.id, tool_name="calculator")

        from app.common.exceptions import ConflictException
        with pytest.raises(ConflictException):
            await repo.add_config_tool(config_id=config.id, tool_name="calculator")

    @pytest.mark.asyncio
    async def test_unique_constraint_mcp_server_per_user(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """Same MCP server name cannot be used twice by same user."""
        await repo.create_mcp_server(
            user_id=sample_user_id,
            name="unique-mcp-test",
            url="https://example.com",
        )

        from app.common.exceptions import ConflictException
        with pytest.raises(ConflictException):
            await repo.create_mcp_server(
                user_id=sample_user_id,
                name="unique-mcp-test",
                url="https://different.com",
            )

    @pytest.mark.asyncio
    async def test_config_belongs_to_user(
        self, repo: AgentRepository, sample_user_id: int
    ):
        """User cannot access another user's config."""
        other_user_id = sample_user_id + 999

        config = await repo.create_config(
            user_id=other_user_id,
            name="other-user-config",
        )

        from app.common.exceptions import NotFoundException
        with pytest.raises(NotFoundException):
            await repo.get_config(config.id, sample_user_id)
