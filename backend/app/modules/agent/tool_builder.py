"""
ToolBuilder - builds Tool instances from DomainConfig.

3-layer architecture:
1. AgentConfigLoader: DB → DomainConfig
2. ToolBuilder: DomainConfig → list[Tool]
3. Agent runtime: uses tools

Error isolation: MCP server failures are collected in warnings, not thrown.
"""

import asyncio

from app.modules.agent.domain import (
    DomainConfig,
    MCPConfigItem,
    ToolConfigItem,
)
from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.builtin_mcp_registry import registry as builtin_registry
from app.modules.agent.mcp.tool import MCPToolConfig, MCPTool
from app.modules.agent.mcp.session import create_session
from app.modules.agent.mcp.exceptions import (
    MCPConnectionError,
    MCPProtocolError,
    MCPValidationError,
)


class ToolBuilder:
    """
    Builds tool instances from domain configuration.

    Handles:
    - Built-in tools (calculator, datetime, websearch)
    - MCP tools (via native MCP SDK)
    - RAG tools (knowledge base retrieval)

    Usage:
        builder = ToolBuilder(rag_service=None)
        tools, warnings = await builder.build(domain_config)
    """

    def __init__(self, rag_service=None):
        """
        Initialize ToolBuilder.

        Args:
            rag_service: RAG service for knowledge base retrieval (optional)
        """
        self.rag_service = rag_service

    async def build(self, config: DomainConfig | None) -> tuple[list[Tool], list[str]]:
        """
        Build tool instances from domain configuration.

        Args:
            config: DomainConfig with tool configurations

        Returns:
            Tuple of (tools, warnings)
            - tools: list of Tool instances to use
            - warnings: list of warning strings for failed tool loads
              (errors are isolated per-tool, not thrown)
        """
        tools: list[Tool] = []
        warnings: list[str] = []

        if not config:
            return [], ["No config provided"]

        # 1. Built-in tools
        for tool_cfg in config.tools:
            if not tool_cfg.enabled:
                continue
            try:
                tool = self._build_builtin(tool_cfg)
                if tool:
                    tools.append(tool)
            except Exception as e:
                warnings.append(f"builtin:{tool_cfg.tool_name} load failed: {e}")

        # 2. MCP tools
        for mcp_cfg in config.mcp_servers:
            if not mcp_cfg.enabled:
                continue
            try:
                mcp_tools = await self._build_mcp(mcp_cfg)
                tools.extend(mcp_tools)
            except MCPConnectionError as e:
                warnings.append(f"mcp:{mcp_cfg.name} connection failed: {e}")
            except MCPProtocolError as e:
                warnings.append(f"mcp:{mcp_cfg.name} protocol error: {e}")
            except MCPValidationError as e:
                warnings.append(f"mcp:{mcp_cfg.name} validation error: {e}")
            except Exception as e:
                warnings.append(f"mcp:{mcp_cfg.name} unexpected error: {e}")

        # 3. RAG tools
        if config.kbs and self.rag_service:
            try:
                rag_tool = self._build_rag(config.kbs)
                tools.append(rag_tool)
            except Exception as e:
                warnings.append(f"rag load failed: {e}")

        return tools, warnings

    def _build_builtin(self, tool_cfg: ToolConfigItem) -> Tool | None:
        """Build a single built-in tool by name."""
        match tool_cfg.tool_name:
            case "calculator" | "datetime" | "rag_retrieval":
                return builtin_registry.create_tool(
                    tool_cfg.tool_name, rag_service=self.rag_service
                )
            case "websearch":
                api_key = tool_cfg.tool_config.get("api_key")
                if not api_key:
                    raise ValueError("websearch requires api_key")
                return _WebSearchToolWrapper(
                    api_key=api_key,
                    search_depth=tool_cfg.tool_config.get("search_depth", "basic"),
                )
            case _:
                return None

    async def _build_mcp(self, mcp_cfg: MCPConfigItem) -> list[Tool]:
        """
        Build MCP tools from a single MCP server.

        Args:
            mcp_cfg: MCP server configuration

        Returns:
            List of Tool instances from the MCP server
        """
        async with create_session(
            transport=mcp_cfg.transport,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        ) as session:
            try:
                result = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                raise MCPConnectionError(
                    f"MCP server {mcp_cfg.name} list_tools() timeout after 30s"
                )

        tool_config = MCPToolConfig(
            mcp_server_id=mcp_cfg.mcp_server_id,
            name=mcp_cfg.name,
            transport=mcp_cfg.transport,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        )

        tools = []
        for t in result.tools:
            input_schema = getattr(t, 'inputSchema', None) or {"type": "object", "properties": {}}
            tools.append(MCPTool(
                config=tool_config,
                tool_name=t.name,
                description=t.description or "",
                input_schema=input_schema,
            ))
        return tools

    def _build_rag(self, kbs: list) -> Tool:
        """Build RAG retrieval tool."""
        from app.modules.agent.tools.rag_tool import RAGRetrievalTool

        kb_ids = [kb.kb_id for kb in kbs]
        tool = RAGRetrievalTool(kb_ids=kb_ids, top_k=5)
        tool.set_rag_service(self.rag_service)
        return tool


# =============================================================================
# Built-in tool wrappers
# =============================================================================


class _WebSearchToolWrapper(Tool):
    """
    Wrapper for web search tool (Tavily).
    """

    name = "websearch"
    description = "网络搜索 (Tavily)"

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            }
        },
        "required": ["query"],
    }

    def __init__(self, api_key: str, search_depth: str = "basic"):
        self.api_key = api_key
        self.search_depth = search_depth

    async def run(self, input: dict) -> dict:
        query = input.get("query")
        if not query:
            return {"error": "query is required"}

        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": self.search_depth,
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                return {
                    "answer": result.get("answer"),
                    "results": result.get("results", [])[:5],
                }
        except httpx.TimeoutException:
            return {"error": "Tavily API timeout (30s)"}
        except httpx.HTTPStatusError as e:
            return {"error": f"Tavily API error: {e.response.status_code}"}
