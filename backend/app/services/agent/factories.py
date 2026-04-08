"""
Factory functions for creating Agent tools.

Creates tool list based on configuration (KB IDs, MCP servers, etc).
"""

from typing import Any

from app.services.agent.tools.adapters import to_mcp_tools
from app.services.agent.tools.base import Tool
from app.services.agent.tools.implementations import (
    CalculatorTool,
    DateTimeTool,
    RAGRetrievalTool,
)


def create_local_tools() -> list[Tool]:
    """
    Create Phase 1 local tools (no external dependencies).

    Returns:
        List of Tool instances
    """
    return [
        CalculatorTool(),
        DateTimeTool(),
    ]


async def create_rag_tools(
    kb_ids: list[str],
    rag_service: Any,
    top_k: int = 5,
) -> list[Tool]:
    """
    Create RAG retrieval tools for given knowledge bases.

    Args:
        kb_ids: List of knowledge base IDs
        rag_service: RAG retrieval service instance
        top_k: Default number of results

    Returns:
        List containing RAGRetrievalTool
    """
    if not kb_ids:
        return []

    tool = RAGRetrievalTool(kb_ids=kb_ids, top_k=top_k)
    tool.set_rag_service(rag_service)
    return [tool]


async def create_mcp_tools(
    servers: list[Any],
) -> list[Tool]:
    """
    Create tools from MCP servers using langchain-mcp-adapters.

    Args:
        servers: List of AgentMCPServer model instances

    Returns:
        List of Tool instances (LangChainToolAdapter wrapped)
    """
    if not servers:
        return []

    try:
        from langchain_mcp_adapters import load_mcp_tools
    except ImportError:
        return []

    tools = []
    for server in servers:
        if not getattr(server, "enabled", True):
            continue

        connection: dict[str, Any] = {
            "url": server.url,
            "headers": (server.headers or {}),
            "transport": server.transport,
        }

        try:
            lc_tools = await load_mcp_tools(
                connection=connection,
                server_name=server.name,
                tool_name_prefix=True,
            )
            tools.extend(to_mcp_tools(lc_tools))
        except Exception as e:
            # Log but don't fail - MCP server might be temporarily unavailable
            import loguru

            logger = loguru.logger
            logger.warning(f"Failed to load MCP tools from {server.name}: {e}")

    return tools


async def create_agent_tools(
    kb_ids: list[str] | None = None,
    rag_service: Any = None,
    include_local: bool = True,
    mcp_servers: list[Any] | None = None,
    top_k: int = 5,
) -> list[Tool]:
    """
    Create complete tool list for Agent.

    Args:
        kb_ids: Knowledge base IDs for RAG (optional)
        rag_service: RAG service for retrieval (required if kb_ids provided)
        include_local: Include calculator/datetime tools
        mcp_servers: List of AgentMCPServer instances for MCP tools
        top_k: Default retrieval top_k

    Returns:
        List of Tool instances
    """
    tools = []

    if include_local:
        tools.extend(create_local_tools())

    if kb_ids and rag_service:
        tools.extend(await create_rag_tools(kb_ids, rag_service, top_k))

    if mcp_servers:
        tools.extend(await create_mcp_tools(mcp_servers))

    return tools
