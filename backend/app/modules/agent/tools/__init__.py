"""
Agent Tools.

Provides tools for the Agent module:
- KnowledgeBaseTool: Query knowledge bases
- WebSearchTool: Web search (Tavily, etc.)
- McpToolWrapper: MCP server tools
"""

from app.modules.agent.tools.base import (
    BaseTool,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
)
from app.modules.agent.tools.knowledge_base import (
    KnowledgeBaseTool,
    create_kb_tools,
)
from app.modules.agent.tools.mcp import (
    McpToolWrapper,
    McpWrappedTool,
    create_mcp_tools,
)
from app.modules.agent.tools.websearch import (
    WebSearchTool,
    create_websearch_tool,
    create_websearch_tool_from_config,
)

__all__ = [
    # Base
    "BaseTool",
    "ToolDefinition",
    "ToolResult",
    "ToolRegistry",
    # Knowledge Base
    "KnowledgeBaseTool",
    "create_kb_tools",
    # Web Search
    "WebSearchTool",
    "create_websearch_tool",
    "create_websearch_tool_from_config",
    # MCP
    "McpToolWrapper",
    "McpWrappedTool",
    "create_mcp_tools",
]
