"""
MCP (Model Context Protocol) tool wrapper for Agent.

Provides tools from MCP servers.

Note: This is a simplified/stub implementation. Full MCP support requires:
1. Proper MCP protocol handshake
2. Tool discovery via MCP protocol
3. Async context manager for SSE/HTTP connections

For production use, consider using an MCP SDK that handles these details.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from app.modules.agent.models import McpConnectionType, McpServer
from app.modules.agent.tools.base import BaseTool, ToolDefinition, ToolResult
from app.utils.encrypt_utils import decrypt_api_key


class McpToolWrapper(BaseTool):
    """
    Wrapper for MCP server tools.

    Wraps an MCP client and exposes its tools as Agent tools.

    Note: This is a simplified implementation. Tool discovery is stubbed
    and will return an empty list until proper MCP protocol support is added.
    """

    def __init__(
        self,
        server_name: str,
        server_url: str,
        connection_type: str = McpConnectionType.SSE.value,
        auth_token: str | None = None,
    ):
        """
        Initialize McpToolWrapper.

        Args:
            server_name: Name of the MCP server
            server_url: URL of the MCP server
            connection_type: Connection type (sse or streamable_http)
            auth_token: Optional auth token
        """
        self.server_name = server_name
        self.server_url = server_url
        self.connection_type = connection_type
        self.auth_token = auth_token
        self._client = None
        self._tools: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Initialize the MCP client and discover tools"""
        if self._client is not None:
            return

        try:
            # Import MCP libraries
            from mcp.client.sse import sse_client
        except ImportError:
            raise ImportError(
                "MCP package not installed. Install with: pip install mcp"
            ) from None

        # Build headers
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        # Create client based on connection type
        # Note: sse_client and streamablehttp_client return async context managers
        if self.connection_type == McpConnectionType.SSE.value:
            self._client = sse_client(url=self.server_url, headers=headers)
        elif self.connection_type == McpConnectionType.STREAMABLE_HTTP.value:
            # Use streamable_http client
            from mcp.client.streamable_http import streamablehttp_client

            self._client = streamablehttp_client(
                url=self.server_url,
                headers=headers,
            )
        else:
            raise ValueError(f"Unknown connection type: {self.connection_type}")

    async def discover_tools(self) -> list[ToolDefinition]:
        """
        Discover available tools from the MCP server.

        Returns:
            List of tool definitions

        Note: This is a stub implementation. Full MCP tool discovery
        requires implementing the MCP protocol's list_tools request.
        """
        # TODO: Implement proper MCP tool discovery via protocol
        # The MCP protocol uses JSON-RPC for tool discovery:
        # 1. Send tools/list request
        # 2. Parse response for tool definitions
        # 3. Convert to ToolDefinition format
        return []

    def get_tool(self, tool_name: str) -> BaseTool | None:
        """
        Get a specific tool from the MCP server.

        Args:
            tool_name: Name of the tool

        Returns:
            McpWrappedTool or None
        """
        if tool_name not in self._tools:
            return None

        tool_info = self._tools[tool_name]
        return McpWrappedTool(
            name=tool_name,
            description=tool_info.get("description", ""),
            input_schema=tool_info.get("inputSchema", {}),
            execute_fn=self._execute_tool,
        )

    async def _execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        """Execute a tool on the MCP server"""
        if not self._client:
            await self.initialize()

        try:
            # Client is an async context manager
            async with self._client as client:
                # TODO: Verify correct MCP client API method name
                # Standard MCP uses client.call_tool()
                result = await client.call_tool(tool_name, arguments)
                return ToolResult.ok(str(result))
        except Exception as e:
            return ToolResult.failure(f"MCP tool execution failed: {str(e)}")

    async def list_tools(self) -> list[str]:
        """List available tool names"""
        return list(self._tools.keys())


class McpWrappedTool(BaseTool):
    """Wrapper for a single MCP tool"""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        execute_fn: Callable[[str, dict[str, Any]], Coroutine[Any, Any, ToolResult]],
    ):
        super().__init__(name, description)
        self.input_schema = input_schema
        self._execute_fn = execute_fn

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the MCP tool"""
        try:
            return await self._execute_fn(self.name, kwargs)
        except Exception as e:
            return ToolResult.failure(f"Tool execution failed: {str(e)}")

    def get_definition(self) -> ToolDefinition:
        """Get tool definition for OpenAI function calling"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.input_schema,
        )


async def create_mcp_tools(
    servers: list[McpServer],
) -> list[BaseTool]:
    """
    Create tools from MCP servers.

    Args:
        servers: List of MCP server configurations

    Returns:
        List of BaseTool instances
    """
    tools = []

    for server in servers:
        if not server.enabled:
            continue

        try:
            # Decrypt auth token if present
            auth_token = None
            if server.encrypted_auth_token:
                auth_token = decrypt_api_key(server.encrypted_auth_token)

            wrapper = McpToolWrapper(
                server_name=server.name,
                server_url=server.url,
                connection_type=server.connection_type,
                auth_token=auth_token,
            )
            await wrapper.initialize()

            # Discover and wrap tools
            tool_defs = await wrapper.discover_tools()
            for tool_def in tool_defs:
                tool = wrapper.get_tool(tool_def.name)
                if tool:
                    tools.append(tool)

        except Exception as e:
            # Log error but continue with other servers
            from loguru import logger

            logger.warning(f"Failed to load MCP server {server.name}: {e}")
            continue

    return tools
