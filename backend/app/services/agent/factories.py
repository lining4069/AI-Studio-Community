"""
Factory functions for creating Agent tools.

Creates tool list based on configuration (KB IDs, etc).
"""

from typing import Any

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


async def create_agent_tools(
    kb_ids: list[str] | None = None,
    rag_service: Any = None,
    include_local: bool = True,
    top_k: int = 5,
) -> list[Tool]:
    """
    Create complete tool list for Agent.

    Args:
        kb_ids: Knowledge base IDs for RAG (optional)
        rag_service: RAG service for retrieval (required if kb_ids provided)
        include_local: Include calculator/datetime tools
        top_k: Default retrieval top_k

    Returns:
        List of Tool instances
    """
    tools = []

    if include_local:
        tools.extend(create_local_tools())

    if kb_ids and rag_service:
        tools.extend(await create_rag_tools(kb_ids, rag_service, top_k))

    return tools
