"""
MCP Provider - MCP Layer 的抽象接口层。

MCP Layer 独立于 Agent 系统，不引用 Tool ABC 或 Agent domain 类。
定义 MCP 协议级别的输入输出 Schema 范式。

适配层（Agent 层）负责：
1. 接入：Provider → Tool(ABC) 接入 Agent 工具系统
2. 转化：Agent Schema ↔ MCP Schema 数据范式转换
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class MCPToolDefinition:
    """
    MCP 工具定义（MCP 协议级别的数据结构）。

    Agent 适配器负责将其转化为 Tool ABC 接口。
    """
    name: str
    description: str
    input_schema: dict  # MCP JSON-RPC schema 格式


class MCPProvider(ABC):
    """
    MCP Provider 抽象接口。

    定义 MCP 协议级别的工具发现和执行契约。
    不继承 Tool ABC，不引用 Agent 系统任何类。
    """

    @property
    @abstractmethod
    def server_name(self) -> str:
        """MCP 服务器名称"""
        ...

    @property
    @abstractmethod
    def transport(self) -> str:
        """传输类型：stdio / sse / streamable_http"""
        ...

    @abstractmethod
    async def list_tools(self) -> list[MCPToolDefinition]:
        """
        发现 MCP 服务器提供的所有工具。

        Returns:
            MCP 协议级别的工具定义列表
        Raises:
            MCPConnectionError: 连接失败
            MCPProtocolError: 协议错误
        """
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, input: dict) -> dict:
        """
        执行指定的 MCP 工具。

        MCP 协议输入：工具名 + JSON-RPC 格式参数
        MCP 协议输出：CallToolResult（MCP 层自行解析）

        Args:
            tool_name: MCP 工具名称
            input: MCP 协议格式的输入参数（dict）

        Returns:
            MCP 协议格式的执行结果（dict）

        Raises:
            MCPToolExecutionError: 执行失败或超时
            MCPConnectionError: 连接失败
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭 Provider，释放资源"""
        ...
