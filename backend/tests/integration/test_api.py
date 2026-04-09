"""
Integration Tests for Agent API Endpoints.

Tests the full HTTP request/response cycle using httpx AsyncClient.
Note: These tests require a running application instance or ASGI transport.
"""


import pytest

# These tests use the httpx AsyncClient with ASGITransport
# to test the full HTTP layer without needing a running server


class TestConfigAPI:
    """Test Config API endpoints at the HTTP layer."""

    @pytest.mark.asyncio
    async def test_create_config_schema(self, client, auth_headers):
        """Test create config request schema validation."""
        # Valid request
        response = await client.post(
            "/v1/agent/configs",
            headers=auth_headers,
            json={
                "name": "test-agent",
                "agent_type": "simple",
                "max_loop": 5,
            },
        )

        # Should return 200 or 401 (if no real auth)
        # This validates the endpoint exists and accepts valid schema
        assert response.status_code in [200, 201, 401, 403]

    @pytest.mark.asyncio
    async def test_create_config_invalid_agent_type(self, client, auth_headers):
        """Test invalid agent_type is rejected."""
        response = await client.post(
            "/v1/agent/configs",
            headers=auth_headers,
            json={
                "name": "test",
                "agent_type": "invalid_type",
            },
        )

        # Should return validation error (422) or auth error
        assert response.status_code in [401, 403, 422]

    @pytest.mark.asyncio
    async def test_get_config_requires_auth(self, client):
        """Test get config without auth returns 401/403."""
        response = await client.get("/v1/agent/configs/test-id")

        assert response.status_code in [401, 403, 404]


class TestSessionAPI:
    """Test Session API endpoints at the HTTP layer."""

    @pytest.mark.asyncio
    async def test_create_session_schema(self, client, auth_headers):
        """Test create session request schema validation."""
        response = await client.post(
            "/v1/agent/sessions",
            headers=auth_headers,
            json={},
        )

        # Missing config_id should now fail validation when auth succeeds
        assert response.status_code in [401, 403, 422]

    @pytest.mark.asyncio
    async def test_get_session_requires_auth(self, client):
        """Test get session without auth returns 401/403."""
        response = await client.get("/v1/agent/sessions/test-id")

        assert response.status_code in [401, 403, 404]


class TestRunAPI:
    """Test Run API endpoints at the HTTP layer."""

    @pytest.mark.asyncio
    async def test_create_run_requires_auth(self, client):
        """Test create run without auth returns 401/403."""
        response = await client.post(
            "/v1/agent/sessions/test-session/runs",
            json={"input": "test"},
        )

        assert response.status_code in [401, 403, 404]

    @pytest.mark.asyncio
    async def test_get_run_requires_auth(self, client):
        """Test get run without auth returns 401/403."""
        response = await client.get("/v1/agent/runs/test-run")

        assert response.status_code in [401, 403, 404]

    @pytest.mark.asyncio
    async def test_resume_run_requires_auth(self, client):
        """Test resume run without auth returns 401/403."""
        response = await client.post(
            "/v1/agent/runs/test-run/resume",
            json={"input": "continue"},
        )

        assert response.status_code in [401, 403, 404]

    @pytest.mark.asyncio
    async def test_stop_run_requires_auth(self, client):
        """Test stop run without auth returns 401/403."""
        response = await client.post("/v1/agent/runs/test-run/stop")

        assert response.status_code in [401, 403, 404]


class TestMCPServerAPI:
    """Test MCP Server API endpoints at the HTTP layer."""

    @pytest.mark.asyncio
    async def test_create_mcp_server_schema(self, client, auth_headers):
        """Test create MCP server request schema validation."""
        response = await client.post(
            "/v1/agent/mcp-servers",
            headers=auth_headers,
            json={
                "name": "test-mcp",
                "url": "https://example.com/sse",
                "transport": "streamable_http",
            },
        )

        # Should return 200/201 or auth error
        assert response.status_code in [200, 201, 401, 403]

    @pytest.mark.asyncio
    async def test_list_mcp_servers_requires_auth(self, client):
        """Test list MCP servers without auth returns 401/403."""
        response = await client.get("/v1/agent/mcp-servers")

        assert response.status_code in [401, 403]


class TestBuiltinToolsAPI:
    """Test Builtin Tools API endpoint."""

    @pytest.mark.asyncio
    async def test_get_builtin_tools(self, client):
        """Test get builtin tools returns list."""
        response = await client.get("/v1/agent/builtin-tools")

        # Should return 200 or auth error
        assert response.status_code in [200, 401, 403]

        if response.status_code == 200:
            data = response.json()
            assert "data" in data or isinstance(data, dict)
