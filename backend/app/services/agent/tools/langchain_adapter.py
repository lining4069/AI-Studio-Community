"""LangChain tool adapter for Agent tools.

This module provides LangChainToolAdapter that wraps LangChain BaseTool
(StructuredTool) to conform to our Tool ABC interface.
"""

from typing import Any, get_origin

from langchain_core.tools import BaseTool

from app.services.agent.tools.base import Tool
from app.services.agent.tools.spec import ToolSpec


class LangChainToolAdapter(Tool):
    """
    Wrap a LangChain BaseTool as a Tool instance.

    This adapter allows MCP tools loaded via langchain-mcp-adapters
    to be used with our Tool ABC interface.

    Attributes:
        name: Tool name (from LangChain tool)
        description: Tool description (from LangChain tool)
        input_schema: JSON Schema extracted from LangChain tool's args_schema
        output_schema: Optional output schema (None for LangChain tools)
        _lc_tool: The underlying LangChain BaseTool instance
    """

    def __init__(self, lc_tool: BaseTool) -> None:
        """
        Initialize LangChainToolAdapter.

        Args:
            lc_tool: LangChain BaseTool (StructuredTool) to wrap
        """
        self._lc_tool = lc_tool
        self.name = lc_tool.name
        self.description = lc_tool.description
        self.input_schema = self._extract_input_schema(lc_tool)
        self.output_schema = None

    def _extract_input_schema(self, lc_tool: BaseTool) -> dict[str, Any]:
        """
        Extract JSON Schema from LangChain tool's args_schema.

        Args:
            lc_tool: LangChain BaseTool

        Returns:
            JSON Schema dict for tool input
        """
        args_schema = lc_tool.args_schema
        if args_schema is None:
            return {"type": "object", "properties": {}}

        # Handle Annotated types (from langchain-core)
        origin = get_origin(args_schema)
        if origin is not None:
            # Annotated[X, ...] - extract X
            pass

        # args_schema can be:
        # 1. A Pydantic BaseModel class
        # 2. A JSON schema dict
        if hasattr(args_schema, "model_json_schema"):
            return args_schema.model_json_schema()
        elif isinstance(args_schema, dict):
            return args_schema
        else:
            return {"type": "object", "properties": {}}

    async def run(self, input: dict) -> dict:
        """
        Execute the tool via LangChain's ainvoke.

        Args:
            input: Tool input parameters

        Returns:
            Tool output as dict with result and optional artifact
        """
        try:
            result = await self._lc_tool.ainvoke(input)
            # LangChain tools return content_and_artifact format
            # result is typically a string or list of content blocks
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def to_spec(self) -> ToolSpec:
        """
        Convert to ToolSpec (standardized contract).

        Returns:
            ToolSpec representing this tool's interface
        """
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
        )
