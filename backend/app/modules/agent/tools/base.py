"""Base classes for Agent tools."""
from abc import ABC, abstractmethod


class Tool(ABC):
    """Abstract base class for Agent tools."""

    name: str
    description: str
    schema: dict

    @abstractmethod
    async def run(self, input: dict) -> dict:
        """Execute the tool with the given input.

        Args:
            input: Tool input parameters matching the schema.

        Returns:
            Tool output as a dictionary.
        """
        ...