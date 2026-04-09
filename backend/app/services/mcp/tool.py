"""
MCP 工具配置数据类。

纯数据结构，不继承 Tool ABC，不引用 Agent 系统任何类。
MCP Layer 内部使用，或被 Agent 适配器引用。
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class MCPToolConfig:
    """
    MCP 工具配置（MCP 层的运行时配置）。

    由 Agent 层的 MCPConfigItem 转化而来，
    包含连接单个 MCP Server 所需的全部传输配置。
    """

    mcp_server_id: str
    name: str  # MCP 服务器名称
    transport: str  # "stdio" | "sse" | "streamable_http"

    # HTTP/SSE 传输
    url: str | None = None
    headers: dict[str, Any] | None = None

    # stdio 传输
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None

    # 超时配置
    call_timeout: float = 10.0  # call_tool 超时（秒）
