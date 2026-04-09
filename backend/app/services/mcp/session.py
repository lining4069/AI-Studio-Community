"""
MCP Session 管理。

使用原生 MCP SDK 创建 session，支持三种传输协议：
- stdio: 进程间通信
- sse: Server-Sent Events
- streamable_http: HTTP 流式传输

资源通过 context manager 自动关闭，顺序：
1. ClientSession（内层）
2. transport 流（外层）
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession, McpError
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client import StdioServerParameters

from app.services.mcp.exceptions import (
    MCPConnectionError,
    MCPProtocolError,
    MCPValidationError,
)


@asynccontextmanager
async def create_session(
    transport: str,
    url: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    headers: dict[str, Any] | None = None,
    timeout: float = 5.0,
    sse_read_timeout: float = 300.0,
) -> AsyncIterator[ClientSession]:
    """
    创建 MCP Session。

    Args:
        transport: 传输类型 ("stdio", "sse", "streamable_http")
        url: SSE/Streamable HTTP 端点
        command: stdio 命令（如 "uv", "python"）
        args: stdio 参数列表
        env: stdio 环境变量
        cwd: stdio 工作目录
        headers: HTTP 请求头
        timeout: 连接超时（秒）
        sse_read_timeout: SSE 读取超时（秒）

    Yields:
        ClientSession

    Raises:
        MCPValidationError: 参数校验失败
        MCPConnectionError: 连接失败
        MCPProtocolError: 协议错误
    """
    # 参数校验
    if transport not in ("stdio", "sse", "streamable_http"):
        raise MCPValidationError(f"Unsupported transport: {transport}")

    if transport in ("sse", "streamable_http") and not url:
        raise MCPValidationError(f"transport={transport} requires 'url'")

    if transport == "stdio" and (not command or not args):
        raise MCPValidationError("transport=stdio requires 'command' and 'args'")

    try:
        if transport == "stdio":
            params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
                cwd=cwd,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

        elif transport == "sse":
            async with sse_client(
                url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

        elif transport == "streamable_http":
            async with streamablehttp_client(url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    except McpError as e:
        # MCP SDK 异常映射到自定义异常体系
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            raise MCPConnectionError(error_msg) from e
        elif "protocol" in error_msg.lower() or "handshake" in error_msg.lower():
            raise MCPProtocolError(error_msg) from e
        else:
            raise MCPConnectionError(error_msg) from e

    except Exception:
        raise
