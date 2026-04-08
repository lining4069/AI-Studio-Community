"""
MCP Module.

提供原生 MCP SDK 集成，替代 langchain-mcp-adapters。
"""

from app.modules.agent.mcp.exceptions import (
    MCPError,
    MCPConnectionError,
    MCPProtocolError,
    MCPToolExecutionError,
    MCPValidationError,
)
from app.modules.agent.mcp.session import create_session
from app.modules.agent.mcp.tool import MCPTool, MCPToolConfig

__all__ = [
    "MCPError",
    "MCPConnectionError",
    "MCPProtocolError",
    "MCPToolExecutionError",
    "MCPValidationError",
    "create_session",
    "MCPTool",
    "MCPToolConfig",
]
