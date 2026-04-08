"""
MCP Tool 运行时封装。

使用原生 MCP SDK，每次 run() 创建临时 session，执行后自动关闭。
支持三种传输协议：stdio / sse / streamable_http
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from app.modules.agent.tools.base import Tool
from app.modules.agent.mcp.session import create_session
from app.modules.agent.mcp.exceptions import (
    MCPConnectionError,
    MCPToolExecutionError,
)


@dataclass
class MCPToolConfig:
    """MCP 工具配置。"""
    mcp_server_id: str
    name: str
    transport: str
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    headers: dict[str, Any] | None = None


class MCPTool(Tool):
    """
    MCP 工具运行时封装。

    注意：不持有 session。每次 run() 创建临时 session。
    """

    name: str
    input_schema: dict
    _call_timeout: float = 10.0  # 工具调用超时（秒）

    def __init__(
        self,
        config: MCPToolConfig,
        tool_name: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        self._config = config
        self._tool_name = tool_name
        self.name = tool_name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}

    async def run(self, input: dict) -> dict:
        try:
            async with create_session(
                transport=self._config.transport,
                url=self._config.url,
                command=self._config.command,
                args=self._config.args,
                env=self._config.env,
                cwd=self._config.cwd,
                headers=self._config.headers,
            ) as session:
                # 使用 asyncio.wait_for 添加 call_tool 超时
                result = await asyncio.wait_for(
                    session.call_tool(self._tool_name, input),
                    timeout=self._call_timeout,
                )
                return self._parse_result(result)

        except asyncio.TimeoutError:
            raise MCPToolExecutionError(
                f"Tool {self._tool_name} timeout after {self._call_timeout}s"
            )
        except MCPConnectionError:
            raise  # 保持原始类型，让 Agent 层区分处理
        except Exception as e:
            raise MCPToolExecutionError(f"Tool {self._tool_name} failed: {e}") from e

    def _parse_result(self, result) -> dict:
        """解析 MCP 返回结果，支持多 content type。"""
        if not hasattr(result, 'content') or not result.content:
            return {"result": str(result) if result else ""}

        outputs = []
        for item in result.content:
            if hasattr(item, 'text'):
                outputs.append(item.text)
            elif hasattr(item, 'data'):
                # binary data
                outputs.append(f"<binary data: {len(item.data)} bytes>")
            else:
                outputs.append(str(item))

        return {"result": "\n".join(outputs)}
