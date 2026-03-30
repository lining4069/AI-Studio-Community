"""
Base tool definitions for Agent module.

Provides the base classes for all tools that can be used by the Agent.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result from tool execution"""

    success: bool
    content: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, content: str, metadata: dict[str, Any] = None) -> "ToolResult":
        return cls(success=True, content=content, metadata=metadata or {})

    @classmethod
    def failure(cls, err_msg: str) -> "ToolResult":
        return cls(success=False, content="", error=err_msg)


@dataclass
class ToolDefinition:
    """Definition of a tool for LLM function calling"""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class BaseTool(ABC):
    """Abstract base class for all tools"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        """
        Execute the tool with given arguments.

        Args:
            query: Query string (optional; tools that don't need it ignore it)
            **kwargs: Additional tool-specific arguments

        Returns:
            ToolResult with execution result
        """
        pass

    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """Get the tool definition for LLM function calling"""
        pass

    def validate_parameters(self, parameters: dict[str, Any]) -> bool:
        """
        Validate parameters against the tool definition.

        Args:
            parameters: Parameters to validate

        Returns:
            True if valid, False otherwise
        """
        definition = self.get_definition()
        required = definition.parameters.get("required", [])

        for req_param in required:
            if req_param not in parameters:
                return False

        return True


# ============================================================================
# Tool Registry
# ============================================================================


class ToolRegistry:
    """Registry for managing available tools"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool"""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools"""
        return list(self._tools.values())

    def get_definitions(self) -> list[ToolDefinition]:
        """Get definitions for all tools"""
        return [tool.get_definition() for tool in self._tools.values()]

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Get OpenAI-formatted tool list"""
        return [
            tool.get_definition().to_openai_format() for tool in self._tools.values()
        ]

    async def execute(self, tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        """Execute a tool by name"""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult.failure(f"Tool '{tool_name}' not found")

        if not tool.validate_parameters(parameters):
            return ToolResult.failure(f"Invalid parameters for tool '{tool_name}'")

        try:
            return await tool.execute(**parameters)
        except Exception as e:
            return ToolResult.failure(f"Tool execution failed: {str(e)}")
