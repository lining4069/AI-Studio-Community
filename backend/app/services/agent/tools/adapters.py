"""
Tool Adapter - Provider-specific tool format conversion.

This module provides adapters to convert ToolSpec into
LLM provider-specific function calling formats.

Currently supported:
- OpenAI (function calling)
- LangChain (MCP tools via langchain-mcp-adapters)
"""

from typing import Any

from langchain_core.tools import BaseTool

from app.services.agent.tools.langchain_adapter import LangChainToolAdapter
from app.services.agent.tools.spec import ToolSpec


def to_openai_tools(specs: list[ToolSpec]) -> list[dict]:
    """
    Convert list of ToolSpecs to OpenAI function calling format.

    Args:
        specs: List of ToolSpec instances

    Returns:
        List of OpenAI tool definitions suitable for LLM function calling.
    """
    return [spec.to_openai_format() for spec in specs]


def to_openai_tool(spec: ToolSpec) -> dict:
    """
    Convert a single ToolSpec to OpenAI function calling format.

    Args:
        spec: ToolSpec instance

    Returns:
        OpenAI tool definition.
    """
    return spec.to_openai_format()


def to_mcp_tools(lc_tools: list[BaseTool]) -> list[Any]:
    """
    Convert LangChain BaseTool list (from langchain-mcp-adapters) to our Tool interface.

    Args:
        lc_tools: List of LangChain BaseTool instances (e.g., from load_mcp_tools)

    Returns:
        List of Tool instances (LangChainToolAdapter wrapped)
    """
    return [LangChainToolAdapter(lc_tool=t) for t in lc_tools]
