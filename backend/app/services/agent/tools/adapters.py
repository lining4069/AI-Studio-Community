"""
Tool Adapter - Provider-specific tool format conversion.

This module provides adapters to convert ToolSpec into
LLM provider-specific function calling formats.

Currently supported:
- OpenAI (function calling)
"""

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
