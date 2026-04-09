"""
MCP Module - 独立的基础设施层。

不引用 Agent 系统的 Tool ABC、DomainConfig 或任何 Agent 层类。

导出：
- MCPProvider: 抽象接口
- create_mcp_provider: 工厂函数，创建原生 SDK 实现
- MCPToolConfig: MCP 工具配置（数据结构）
- 异常类
"""

from app.modules.agent.mcp.provider import MCPProvider, MCPToolDefinition
from app.modules.agent.mcp.native_provider import create_mcp_provider
from app.modules.agent.mcp.tool import MCPToolConfig
from app.modules.agent.mcp.exceptions import (
    MCPError,
    MCPConnectionError,
    MCPProtocolError,
    MCPToolExecutionError,
    MCPValidationError,
)

__all__ = [
    # 抽象接口
    "MCPProvider",
    "MCPToolDefinition",
    # 工厂函数
    "create_mcp_provider",
    # 配置数据类
    "MCPToolConfig",
    # 异常
    "MCPError",
    "MCPConnectionError",
    "MCPProtocolError",
    "MCPToolExecutionError",
    "MCPValidationError",
]
