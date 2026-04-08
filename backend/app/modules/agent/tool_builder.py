"""
ToolBuilder - builds Tool instances from DomainConfig.

3-layer architecture:
1. AgentConfigLoader: DB → DomainConfig
2. ToolBuilder: DomainConfig → list[Tool]
3. Agent runtime: uses tools

Error isolation: MCP server failures are collected in warnings, not thrown.
"""

from app.modules.agent.domain import (
    DomainConfig,
    MCPConfigItem,
    ToolConfigItem,
)
from app.modules.agent.tools.base import Tool


class ToolBuilder:
    """
    Builds tool instances from domain configuration.

    Handles:
    - Built-in tools (calculator, datetime, websearch)
    - MCP tools (via langchain-mcp-adapters)
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
            try:
                mcp_tools = await self._build_mcp(mcp_cfg)
                tools.extend(mcp_tools)
            except Exception as e:
                # Single MCP failure doesn't affect other tools
                warnings.append(f"mcp:{mcp_cfg.name} load failed: {e}")

        # 3. RAG tools
        if config.kbs and self.rag_service:
            try:
                rag_tool = self._build_rag(config.kbs)
                tools.append(rag_tool)
            except Exception as e:
                warnings.append(f"rag load failed: {e}")

        return tools, warnings

    def _build_builtin(self, tool_cfg: ToolConfigItem) -> Tool | None:
        """
        Build a single built-in tool by name.

        Args:
            tool_cfg: Tool configuration including name and config dict

        Returns:
            Tool instance or None if tool name unknown
        """
        match tool_cfg.tool_name:
            case "calculator":
                return _CalculatorToolWrapper()
            case "datetime":
                return _DateTimeToolWrapper()
            case "websearch":
                api_key = tool_cfg.tool_config.get("api_key")
                if not api_key:
                    raise ValueError("websearch requires api_key in tool_config")
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
        from app.services.agent.adapters.langchain_mcp import to_mcp_tools

        try:
            from langchain_mcp_adapters import load_mcp_tools
        except ImportError:
            return []

        connection: dict = {
            "url": mcp_cfg.url,
            "headers": (mcp_cfg.headers or {}),
            "transport": mcp_cfg.transport,
        }

        lc_tools = await load_mcp_tools(
            connection=connection,
            server_name=mcp_cfg.name,
            tool_name_prefix=True,
        )

        return to_mcp_tools(lc_tools)

    def _build_rag(self, kbs: list) -> Tool:
        """
        Build RAG retrieval tool.

        Args:
            kbs: List of KB config items

        Returns:
            RAG retrieval tool instance
        """
        from app.modules.agent.tools.rag_tool import RAGRetrievalTool

        kb_ids = [kb.kb_id for kb in kbs]
        tool = RAGRetrievalTool(kb_ids=kb_ids, top_k=5)
        tool.set_rag_service(self.rag_service)
        return tool


# =============================================================================
# Built-in tool wrappers (import from modules/agent/tools)
# =============================================================================


class _CalculatorToolWrapper(Tool):
    """Wrapper for built-in calculator tool."""

    name = "calculator"
    description = "数学计算工具"
    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式",
            }
        },
        "required": ["expression"],
    }

    async def run(self, input: dict) -> dict:
        from app.modules.agent.tools.calculator import CalculatorTool

        tool = CalculatorTool()
        return await tool.run(input)


class _DateTimeToolWrapper(Tool):
    """Wrapper for built-in datetime tool."""

    name = "datetime"
    description = "当前日期时间"
    input_schema = {
        "type": "object",
        "properties": {},
    }

    async def run(self, input: dict) -> dict:
        from app.modules.agent.tools.datetime import DateTimeTool

        tool = DateTimeTool()
        return await tool.run(input)


class _WebSearchToolWrapper(Tool):
    """
    Wrapper for web search tool (Tavily).

    Uses httpx with 30s timeout for production safety.
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
