"""Base classes for Agent tools."""

from abc import ABC, abstractmethod

from app.modules.agent.tools.spec import ToolSpec


class Tool(ABC):
    """Abstract base class for Agent tools."""

    name: str
    description: str
    input_schema: dict
    output_schema: dict | None = None

    @abstractmethod
    async def run(self, input: dict) -> dict:
        """Execute the tool with the given input.

        Args:
            input: Tool input parameters matching the schema.

        Returns:
            Tool output as a dictionary.
        """
        ...

    def to_spec(self) -> ToolSpec:
        """
        Convert Tool to ToolSpec (standardized contract).

        This enables provider-agnostic tool description.

        Returns:
            ToolSpec representing this tool's interface.
        """
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
        )

    # Legacy alias for backward compatibility
    @property
    def schema(self) -> dict:
        """Legacy alias for input_schema (for backward compatibility)."""
        return self.input_schema
