"""Tool registry for managing and accessing Agent tools."""
from collections.abc import Iterable

from app.modules.agent.tools.base import Tool


class ToolRegistry:
    """
    Central registry for Agent tools.

    Tools are registered by name and can be retrieved or listed
    for LLM function calling.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by its name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name, returns None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """
        Return list of tool definitions for LLM function calling.

        Returns:
            List of dicts with name, description, parameters keys.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.schema,
            }
            for t in self._tools.values()
        ]

    @property
    def tools(self) -> Iterable[Tool]:
        """Return all registered tools."""
        return self._tools.values()