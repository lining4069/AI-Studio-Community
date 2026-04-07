"""
ToolSpec - Standardized contract for Agent tools.

This module defines the normalized contract (ToolSpec) that is
independent of any LLM provider. Providers (OpenAI, Anthropic, etc.)
convert ToolSpec to their specific formats.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    """
    Standardized tool contract.

    ToolSpec is a provider-agnostic representation of a tool's interface.
    It normalizes how tools describe their inputs/outputs for LLM consumption.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        input_schema: JSON Schema for tool input parameters
        output_schema: Optional JSON Schema for tool output
        metadata: Additional provider-agnostic metadata
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_openai_format(self) -> dict:
        """
        Convert to OpenAI function calling format.

        Returns:
            OpenAI tool definition with "type": "function" structure.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ToolSpec":
        """Create ToolSpec from dict."""
        return cls(
            name=data["name"],
            description=data["description"],
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema"),
            metadata=data.get("metadata", {}),
        )
