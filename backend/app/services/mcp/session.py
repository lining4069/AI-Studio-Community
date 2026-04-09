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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession, McpError
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from app.services.mcp.exceptions import (
    MCPConnectionError,
    MCPProtocolError,
    MCPValidationError,
)


def _require_str(value: str | None, field_name: str) -> str:
    """Narrow optional string after transport-specific validation."""
    if value is None:
        raise MCPValidationError(f"{field_name} is required")
    return value


def _require_str_list(value: list[str] | None, field_name: str) -> list[str]:
    """Narrow optional string list after transport-specific validation."""
    if value is None:
        raise MCPValidationError(f"{field_name} is required")
    return value


def _iter_leaf_exceptions(exc: BaseException) -> list[BaseException]:
    """Flatten nested exception groups into leaf exceptions."""
    if isinstance(exc, BaseExceptionGroup):
        leaves: list[BaseException] = []
        for child in exc.exceptions:
            leaves.extend(_iter_leaf_exceptions(child))
        return leaves
    return [exc]


def _is_cleanup_noise(exc: BaseException) -> bool:
    """Ignore teardown noise when a more useful root cause is available."""
    return isinstance(exc, (BrokenPipeError, ConnectionResetError))


def _pick_root_exception(exc: BaseException) -> BaseException:
    """Choose the most actionable exception from a nested failure."""
    leaves = _iter_leaf_exceptions(exc)
    meaningful = [leaf for leaf in leaves if not _is_cleanup_noise(leaf)]
    return meaningful[0] if meaningful else leaves[0]


def _describe_exception(exc: BaseException) -> str:
    """Convert transport/library exceptions into user-facing diagnostics."""
    root = _pick_root_exception(exc)

    if isinstance(root, httpx.HTTPStatusError):
        response = root.response
        request = root.request
        return (
            f"HTTP {response.status_code} {response.reason_phrase} "
            f"while connecting to {request.url}"
        )

    if isinstance(root, httpx.TimeoutException):
        return "Connection timeout"

    if isinstance(root, httpx.RequestError):
        request = root.request
        if request is not None:
            return f"Connection error for {request.url}: {root}"
        return f"Connection error: {root}"

    return str(root)


def _raise_mcp_error(exc: BaseException) -> None:
    """Map SDK/runtime exceptions into MCP-specific exceptions."""
    if isinstance(exc, TimeoutError):
        raise MCPConnectionError("Connection timeout") from exc

    if isinstance(exc, OSError):
        raise MCPConnectionError(f"Connection error: {exc}") from exc

    if isinstance(exc, McpError):
        error_msg = _describe_exception(exc)
        if "protocol" in error_msg.lower() or "handshake" in error_msg.lower():
            raise MCPProtocolError(error_msg) from exc
        raise MCPConnectionError(error_msg) from exc

    error_msg = _describe_exception(exc)
    if "protocol" in error_msg.lower() or "handshake" in error_msg.lower():
        raise MCPProtocolError(error_msg) from exc
    raise MCPConnectionError(error_msg) from exc


@asynccontextmanager
async def create_session(
    transport: str,
    url: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    headers: dict[str, Any] | None = None,
    timeout: float = 5.0,  # noqa: ASYNC109
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
            command_value = _require_str(command, "command")
            args_value = _require_str_list(args, "args")
            params = StdioServerParameters(
                command=command_value,
                args=args_value,
                env=env,
                cwd=cwd,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

        elif transport == "sse":
            url_value = _require_str(url, "url")
            async with sse_client(
                url_value,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

        elif transport == "streamable_http":
            url_value = _require_str(url, "url")
            async with httpx.AsyncClient(
                headers=headers or {},
                timeout=httpx.Timeout(timeout),
            ) as http_client:
                async with streamable_http_client(
                    url_value,
                    http_client=http_client,
                    terminate_on_close=True,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        yield session

    except Exception as e:
        _raise_mcp_error(e)
