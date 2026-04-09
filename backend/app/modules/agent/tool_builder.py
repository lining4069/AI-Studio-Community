"""
ToolBuilder - builds Tool instances from DomainConfig.

3-layer architecture:
1. AgentConfigLoader: DB → DomainConfig
2. ToolBuilder: DomainConfig → list[Tool]
3. Agent runtime: uses tools

MCP 接入（Phase 5 重构）：
- MCP Layer (mcp/) 定义 MCPProvider 接口，与 Agent 系统无关
- ToolBuilder 创建 MCPToolAdapter，将 MCP Provider 接入 Tool ABC
- MCPToolAdapter 负责：接入 (Provider→Tool) + 数据转化 (Schema 映射)
"""

import asyncio

from app.modules.agent.domain import (
    DomainConfig,
    MCPConfigItem,
    ToolConfigItem,
)
from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.builtin_mcp_registry import registry as builtin_registry
from app.modules.agent.mcp import (
    MCPProvider,
    MCPToolDefinition,
    create_mcp_provider,
    MCPConnectionError,
    MCPProtocolError,
    MCPValidationError,
    MCPToolExecutionError,
)


class ToolBuilder:
    """
    Builds tool instances from domain configuration.

    Handles:
    - Built-in tools (calculator, datetime, websearch)
    - MCP tools (via MCPProvider interface → MCPToolAdapter)
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

        # 2. MCP tools (via Provider interface)
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
        Build MCP tools from a single MCP server via Provider interface.

        流程：
        1. create_mcp_provider() 创建 NativeMCPProvider（MCP Layer 内部）
        2. provider.list_tools() 发现工具列表
        3. 为每个工具创建 MCPToolAdapter（Agent 层适配器）

        Args:
            mcp_cfg: MCP server configuration (Agent domain)

        Returns:
            List of Tool instances (MCPToolAdapter)
        """
        # 1. 创建 Provider（MCP Layer）
        provider = create_mcp_provider(
            transport=mcp_cfg.transport,
            server_name=mcp_cfg.name,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        )

        # 2. 发现工具列表（通过 Provider 接口）
        tool_defs = await provider.list_tools()

        # 3. 创建适配器：将 MCP Provider 接入 Tool ABC
        adapters = []
        for tool_def in tool_defs:
            adapters.append(
                MCPToolAdapter(
                    provider=provider,
                    tool_def=tool_def,
                )
            )
        return adapters

    def _build_rag(self, kbs: list) -> Tool:
        """Build RAG retrieval tool."""
        from app.modules.agent.tools.rag_tool import RAGRetrievalTool

        kb_ids = [kb.kb_id for kb in kbs]
        tool = RAGRetrievalTool(kb_ids=kb_ids, top_k=5)
        tool.set_rag_service(self.rag_service)
        return tool


# =============================================================================
# MCP Tool Adapter (Agent 层) - 将 MCP Provider 接入 Tool ABC
# =============================================================================


class MCPToolAdapter(Tool):
    """
    MCP 工具适配器：将 MCP Provider 接入 Agent 的 Tool ABC 接口。

    双重职责：
    1. 接入：Provider.call_tool() → Tool.run()，让 Agent Runtime 能调用 MCP 工具
    2. 转化：MCP Schema ↔ Agent Schema 数据范式（当前为直通，未来可扩展映射）

    此适配器属于 Agent 层，不知道 MCP Layer 内部实现。
    """

    name: str
    description: str
    input_schema: dict

    def __init__(
        self,
        provider: MCPProvider,
        tool_def: MCPToolDefinition,
    ):
        self._provider = provider
        self._tool_def = tool_def

        # Tool ABC 属性
        self.name = tool_def.name
        self.description = tool_def.description
        self.input_schema = tool_def.input_schema

    async def run(self, input: dict) -> dict:
        """
        执行 MCP 工具。

        调用流程：
        Provider.call_tool() → MCP Native SDK → MCP Server
        """
        try:
            result = await self._provider.call_tool(self.name, input)
            return self._adapt_output(result)
        except MCPToolExecutionError:
            raise
        except MCPConnectionError:
            raise
        except Exception as e:
            raise MCPToolExecutionError(
                f"Tool {self.name} failed: {e}"
            ) from e

    def _adapt_output(self, mcp_result: dict) -> dict:
        """
        数据转化：MCP 输出格式 → Agent Tool 输出格式。

        当前为直通（Phase 5），不改变数据范式。
        未来可在此扩展：结果映射、格式化、过滤等。
        """
        return mcp_result


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
