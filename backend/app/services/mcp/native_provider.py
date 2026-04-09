"""
Native MCP Provider - MCP Python Native SDK 实现。

实现 MCPProvider 接口，通过原生 MCP SDK 进行：
- 工具发现（list_tools）
- 工具执行（call_tool）

传输协议：stdio / sse / streamable_http
"""

import asyncio
from typing import Any

from mcp import ClientSession

from app.services.mcp.provider import MCPProvider, MCPToolDefinition
from app.services.mcp.session import create_session
from app.services.mcp.exceptions import (
    MCPConnectionError,
    MCPProtocolError,
    MCPToolExecutionError,
)


class NativeMCPProvider(MCPProvider):
    """
    MCP 原生 SDK 实现。

    持有 MCP 连接会话，工具发现和执行都通过原生 SDK。
    Per-call 模式：每次 call_tool 创建新 session（保持 Phase 5 行为）。
    """

    def __init__(
        self,
        transport: str,
        server_name: str,
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        headers: dict[str, Any] | None = None,
        call_timeout: float = 10.0,
    ):
        self._transport = transport
        self._server_name = server_name
        self._url = url
        self._command = command
        self._args = args
        self._env = env
        self._cwd = cwd
        self._headers = headers
        self._call_timeout = call_timeout

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def transport(self) -> str:
        return self._transport

    async def list_tools(self) -> list[MCPToolDefinition]:
        """通过 MCP SDK 发现工具"""
        async with create_session(
            transport=self._transport,
            url=self._url,
            command=self._command,
            args=self._args,
            env=self._env,
            cwd=self._cwd,
            headers=self._headers,
        ) as session:
            try:
                result = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                raise MCPConnectionError(
                    f"MCP server {self._server_name} list_tools() timeout after 30s"
                )

        tools = []
        for t in result.tools:
            input_schema = getattr(t, 'inputSchema', None) or {
                "type": "object",
                "properties": {}
            }
            tools.append(MCPToolDefinition(
                name=t.name,
                description=t.description or "",
                input_schema=input_schema,
            ))
        return tools

    async def call_tool(self, tool_name: str, input: dict) -> dict:
        """通过 MCP SDK 执行工具"""
        async with create_session(
            transport=self._transport,
            url=self._url,
            command=self._command,
            args=self._args,
            env=self._env,
            cwd=self._cwd,
            headers=self._headers,
        ) as session:
            try:
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, input),
                    timeout=self._call_timeout,
                )
            except asyncio.TimeoutError:
                raise MCPToolExecutionError(
                    f"Tool {tool_name} timeout after {self._call_timeout}s"
                )
            except MCPConnectionError:
                raise
            except Exception as e:
                raise MCPToolExecutionError(
                    f"Tool {tool_name} failed: {e}"
                ) from e

        return self._parse_result(result)

    def _parse_result(self, result) -> dict:
        """解析 MCP CallToolResult，支持多 content type"""
        if not hasattr(result, 'content') or not result.content:
            return {"result": str(result) if result else ""}

        outputs = []
        for item in result.content:
            if hasattr(item, 'text'):
                outputs.append(item.text)
            elif hasattr(item, 'data'):
                outputs.append(f"<binary data: {len(item.data)} bytes>")
            else:
                outputs.append(str(item))

        return {"result": "\n".join(outputs)}

    async def close(self) -> None:
        """Per-call 模式不需要主动关闭，context manager 处理"""
        pass


def create_mcp_provider(
    transport: str,
    server_name: str,
    url: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    headers: dict[str, Any] | None = None,
    call_timeout: float = 10.0,
) -> NativeMCPProvider:
    """
    工厂函数：根据配置创建 NativeMCPProvider 实例。

    此函数作为 MCP Layer 对外的唯一构造入口。
    Agent 适配器通过此函数创建 Provider，不直接引用 NativeMCPProvider。
    """
    return NativeMCPProvider(
        transport=transport,
        server_name=server_name,
        url=url,
        command=command,
        args=args,
        env=env,
        cwd=cwd,
        headers=headers,
        call_timeout=call_timeout,
    )
