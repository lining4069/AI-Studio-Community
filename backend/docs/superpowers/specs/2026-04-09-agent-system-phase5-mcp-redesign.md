# Agent System Phase 5 — MCP Native SDK 重构

**日期**: 2026-04-09
**状态**: Draft v6（修复阻断级问题）
**Phase**: Phase 5

---

## 1. 概述

Phase 5 移除 `langchain-mcp-adapters`，使用原生 Python MCP SDK 实现 MCP 工具集成。

### 核心设计

```
per-call session 模式：
每次 tool.run() 创建临时 session，执行后自动关闭。

优点：简单、错误隔离、无连接泄漏
缺点：高频调用有开销
```

### v6 修正（基于工程评审）

| 问题 | 修正 |
|------|------|
| `stdio_client` 未导入 | 添加 `from mcp.client.stdio import stdio_client` |
| MCP 异常未映射 | `create_session` 中捕获 `McpError` 并转换 |
| `_build_mcp` 未过滤 `enabled` | 添加 `if not mcp_cfg.enabled: continue` |
| `_parse_result` 过于脆弱 | 支持多 content type 解析 |
| `call_tool` 无 timeout | 用 `asyncio.wait_for` 包装 |

---

## 2. create_session

```python
# app/modules/agent/mcp/session.py

from contextlib import asynccontextmanager
from mcp import ClientSession, McpError, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client  # ← 修复：添加 stdio_client 导入
from mcp.client.streamable_http import streamablehttp_client
from typing import Any, AsyncIterator

class MCPConnectionError(Exception): pass
class MCPProtocolError(Exception): pass
class MCPToolExecutionError(Exception): pass
class MCPValidationError(Exception): pass


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

    资源通过 context manager 自动关闭，顺序：
    1. ClientSession（内层）
    2. transport 流（外层）
    """
    if transport not in ("stdio", "sse", "streamable_http"):
        raise MCPValidationError(f"Unsupported transport: {transport}")

    if transport in ("sse", "streamable_http") and not url:
        raise MCPValidationError(f"transport={transport} requires 'url'")
    if transport == "stdio" and (not command or not args):
        raise MCPValidationError("transport=stdio requires 'command' and 'args'")

    try:
        if transport == "stdio":
            params = StdioServerParameters(
                command=command, args=args, env=env, cwd=cwd,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

        elif transport == "sse":
            async with sse_client(
                url, headers=headers, timeout=timeout, sse_read_timeout=sse_read_timeout,
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
        # ← 修复：MCP SDK 异常映射到自定义异常体系
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            raise MCPConnectionError(error_msg) from e
        elif "protocol" in error_msg.lower() or "handshake" in error_msg.lower():
            raise MCPProtocolError(error_msg) from e
        else:
            raise MCPConnectionError(error_msg) from e
    except Exception:
        raise
```

---

## 3. MCPTool

```python
# app/modules/agent/mcp/tool.py

import asyncio
from dataclasses import dataclass
from typing import Any

from app.modules.agent.tools.base import Tool
from app.services.mcp.session import create_session, MCPConnectionError


@dataclass
class MCPToolConfig:
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

    # ← 修复：添加 class 级默认值
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
                # ← 修复：用 asyncio.wait_for 添加 call_tool 超时
                result = await asyncio.wait_for(
                    session.call_tool(self._tool_name, input),
                    timeout=self._call_timeout,
                )
                return self._parse_result(result)

        except asyncio.TimeoutError:
            # 超时转换为工具执行错误
            from app.services.mcp.exceptions import MCPToolExecutionError
            raise MCPToolExecutionError(
                f"Tool {self._tool_name} timeout after {self._call_timeout}s"
            )
        except MCPConnectionError:
            raise  # 保持原始类型，让 Agent 层区分处理
        except Exception as e:
            from app.services.mcp.exceptions import MCPToolExecutionError
            raise MCPToolExecutionError(f"Tool {self._tool_name} failed: {e}") from e

    def _parse_result(self, result) -> dict:
        # ← 修复：健壮的多 content type 解析
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
```

---

## 4. 内置 MCP 注册表

### 4.1 builtin_mcp_registry.py

```python
# app/modules/agent/tools/builtin_mcp_registry.py

from typing import Any
from app.modules.agent.tools.base import Tool


class BuiltinMCPRegistry:
    """内置 MCP 注册表（模块级单例）"""

    def __init__(self):
        self._specs: dict[str, dict] = {}

    def register(self, name: str, spec: dict) -> None:
        self._specs[name] = spec

    def get(self, name: str) -> dict | None:
        return self._specs.get(name)

    def create_tool(self, name: str, rag_service=None) -> "BuiltinMCPTool | None":
        spec = self.get(name)
        if not spec:
            return None
        return BuiltinMCPTool(spec=spec, rag_service=rag_service)


class BuiltinMCPTool(Tool):
    """内置 MCP 运行时工具"""
    name: str
    description: str
    input_schema: dict

    def __init__(self, spec: dict, rag_service=None):
        self._spec = spec
        self.rag_service = rag_service
        self.name = spec["name"]
        self.description = spec["description"]
        self.input_schema = spec["input_schema"]

    async def run(self, input: dict) -> dict:
        handler = self._spec["handler"]
        return await handler(input, self.rag_service)


# 模块级单例
registry = BuiltinMCPRegistry()
```

### 4.2 builtin_mcp_specs.py

```python
# app/modules/agent/tools/builtin_mcp_specs.py

from datetime import datetime
import ast
import operator

from app.modules.agent.tools.builtin_mcp_registry import registry


async def calculator_handler(input: dict, rag_service) -> dict:
    expression = input.get("expression", "")
    safe_ops = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op in safe_ops:
                return safe_ops[op](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp):
            op = type(node.op)
            if op in safe_ops:
                return safe_ops[op](eval_node(node.operand))
        raise ValueError(f"Unsupported: {type(node).__name__}")

    try:
        parsed = ast.parse(expression, mode='eval')
        return {"result": eval_node(parsed.body)}
    except Exception as e:
        return {"error": f"Calculation error: {e}"}


async def datetime_handler(input: dict, rag_service) -> dict:
    now = datetime.now()
    return {"result": {"date": now.isoformat(), "timestamp": now.timestamp()}}


async def rag_handler(input: dict, rag_service) -> dict:
    if not rag_service:
        return {"error": "RAG service not available"}
    query = input.get("query", "")
    results = await rag_service.retrieve(query, top_k=5)
    return {"result": results}


registry.register("calculator", {
    "name": "calculator",
    "description": "Mathematical calculator",
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "Math expression"}},
        "required": ["expression"]
    },
    "handler": calculator_handler,
})

registry.register("datetime", {
    "name": "datetime",
    "description": "Get current date and time",
    "input_schema": {"type": "object", "properties": {}},
    "handler": datetime_handler,
})

registry.register("rag_retrieval", {
    "name": "rag_retrieval",
    "description": "Knowledge base retrieval",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"]
    },
    "handler": rag_handler,
})
```

### 4.3 __init__.py（触发注册）

```python
# app/modules/agent/tools/__init__.py

from app.modules.agent.tools.builtin_mcp_registry import registry
from app.modules.agent.tools import builtin_mcp_specs  # noqa: F401 - 触发注册
```

---

## 5. ToolBuilder

```python
# app/modules/agent/tool_builder.py

from app.modules.agent.domain import DomainConfig, MCPConfigItem, ToolConfigItem
from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.builtin_mcp_registry import registry as builtin_registry
from app.services.mcp.tool import MCPToolConfig, MCPTool
from app.services.mcp.session import create_session
from app.services.mcp.exceptions import (
    MCPConnectionError, MCPProtocolError, MCPValidationError,
)


class ToolBuilder:
    def __init__(self, rag_service=None):
        self.rag_service = rag_service
        self._builtin_registry = builtin_registry

    async def build(self, config: DomainConfig | None) -> tuple[list[Tool], list[str]]:
        tools: list[Tool] = []
        warnings: list[str] = []

        if not config:
            return [], ["No config provided"]

        # 1. 内置工具
        for tool_cfg in config.tools:
            if not tool_cfg.enabled:
                continue
            try:
                tool = self._build_builtin(tool_cfg)
                if tool:
                    tools.append(tool)
            except Exception as e:
                warnings.append(f"builtin:{tool_cfg.tool_name} load failed: {e}")

        # 2. MCP 工具
        for mcp_cfg in config.mcp_servers:
            # ← 修复：过滤 disabled 的 MCP server
            if not mcp_cfg.enabled:
                continue
            try:
                mcp_tools = await self._build_mcp(mcp_cfg)
                tools.extend(mcp_tools)
            except MCPConnectionError as e:
                warnings.append(f"mcp:{mcp_cfg.name} connection failed: {e}")
            except MCPProtocolError as e:
                warnings.append(f"mcp:{mcp_cfg.name} protocol error: {e}")
            except MCPValidationError as e:
                warnings.append(f"mcp:{mcp_cfg.name} validation error: {e}")
            except Exception as e:
                warnings.append(f"mcp:{mcp_cfg.name} unexpected error: {e}")

        # 3. RAG 工具
        if config.kbs and self.rag_service:
            rag_tool = self._build_rag(config.kbs)
            tools.append(rag_tool)

        return tools, warnings

    def _build_builtin(self, tool_cfg: ToolConfigItem) -> Tool | None:
        match tool_cfg.tool_name:
            case "calculator" | "datetime":
                return self._builtin_registry.create_tool(
                    tool_cfg.tool_name, rag_service=self.rag_service
                )
            case "websearch":
                api_key = tool_cfg.tool_config.get("api_key")
                if not api_key:
                    raise ValueError("websearch requires api_key")
                return _WebSearchToolWrapper(api_key=api_key)
            case _:
                return None

    async def _build_mcp(self, mcp_cfg: MCPConfigItem) -> list[Tool]:
        async with create_session(
            transport=mcp_cfg.transport,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        ) as session:
            result = await session.list_tools()

        tool_config = MCPToolConfig(
            mcp_server_id=mcp_cfg.mcp_server_id,
            name=mcp_cfg.name,
            transport=mcp_cfg.transport,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        )

        tools = []
        for t in result.tools:
            input_schema = getattr(t, 'inputSchema', None) or {"type": "object", "properties": {}}
            tools.append(MCPTool(
                config=tool_config,
                tool_name=t.name,
                description=t.description or "",
                input_schema=input_schema,
            ))
        return tools

    def _build_rag(self, kbs: list) -> Tool:
        from app.modules.agent.tools.rag_tool import RAGRetrievalTool
        kb_ids = [kb.kb_id for kb in kbs]
        tool = RAGRetrievalTool(kb_ids=kb_ids, top_k=5)
        tool.set_rag_service(self.rag_service)
        return tool
```

---

## 6. 数据模型

```python
class AgentMCPServer(Base, TimestampMixin):
    __tablename__ = "agent_mcp_servers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transport: Mapped[str] = mapped_column(String(20), default="streamable_http")

    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    command: Mapped[str | None] = mapped_column(String(100), nullable=True)
    args: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    env: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cwd: Mapped[str | None] = mapped_column(String(500), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

---

## 7. API Schema

```python
# app/modules/agent/schema.py

from pydantic import BaseModel, model_validator

class MCPServerCreate(BaseModel):
    name: str
    transport: str = "streamable_http"
    url: str | None = None
    headers: dict | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict | None = None
    cwd: str | None = None

    @model_validator(mode='after')
    def validate_transport_fields(self):
        if self.transport in ("sse", "streamable_http") and not self.url:
            raise ValueError(f"transport={self.transport} requires 'url'")
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("transport=stdio requires 'command'")
            if not self.args:
                raise ValueError("transport=stdio requires 'args'")
        return self


class MCPTestResponse(BaseModel):
    status: str
    transport: str
    tools: list[dict]
    error: str | None = None
    latency_ms: float
```

---

## 8. 异常处理

```python
# app/modules/agent/mcp/exceptions.py

class MCPError(Exception): pass
class MCPConnectionError(MCPError): pass
class MCPProtocolError(MCPError): pass
class MCPToolExecutionError(MCPError): pass
class MCPValidationError(MCPError): pass
```

### Agent 层处理

```python
# Agent 层捕获并处理工具失败
try:
    result = await tool.run(input)
except MCPConnectionError:
    # 连接失败：可重试
    raise
except MCPToolExecutionError:
    # 执行失败：通常不重试
    return {"error": f"Tool execution failed"}
```

---

## 9. 移除依赖

```diff
# pyproject.toml
dependencies = [
-   "langchain-mcp-adapters>=0.2.2",
    "mcp>=1.27.0",
]
```

---

## 10. 实现步骤

1. 创建 `app/modules/agent/mcp/exceptions.py`
2. 创建 `app/modules/agent/mcp/session.py`（含 MCP 异常映射）
3. 创建 `app/modules/agent/mcp/tool.py`（含 timeout + 健壮解析）
4. 创建 `app/modules/agent/tools/builtin_mcp_registry.py`
5. 创建 `app/modules/agent/tools/builtin_mcp_specs.py`
6. 更新 `app/modules/agent/tools/__init__.py`
7. 重构 `app/modules/agent/tool_builder.py`（含 enabled 过滤）
8. 更新 `app/modules/agent/models.py` (AgentMCPServer)
9. 更新 `app/modules/agent/schema.py`
10. 数据库迁移
11. 删除 `app/services/agent/adapters/langchain_mcp.py`
12. 测试验证

---

## 11. 验证清单

### 正向测试
- [ ] `streamable_http` 传输
- [ ] `sse` 传输
- [ ] `stdio` 传输（uv run）
- [ ] `calculator` 内置工具
- [ ] `datetime` 内置工具
- [ ] `rag_retrieval` 内置工具
- [ ] RAG 工具
- [ ] 单个 MCP Server 失败不影响其他工具

### 负向测试
- [ ] `transport=sse` 无 `url` → 验证错误
- [ ] `transport=stdio` 无 `command` → 验证错误
- [ ] `transport=stdio` 无 `args` → 验证错误
- [ ] `cwd` 字段正确传递

### 错误处理
- [ ] MCP 连接失败 → warning，不阻塞 Agent
- [ ] MCP 协议错误 → warning，不阻塞 Agent
- [ ] 工具执行超时 → `MCPToolExecutionError`
- [ ] 多 content type 解析正确

### 回归测试
- [ ] 移除 `langchain-mcp-adapters` 后无 ImportError
- [ ] 现有 Agent 执行流程不受影响

---

## 12. Phase 边界

### Phase 5 包含
- ✅ 移除 `langchain-mcp-adapters`
- ✅ 原生 MCP SDK 集成
- ✅ stdio/sse/streamable_http 传输
- ✅ 内置 MCP 注册表
- ✅ 正确的 session 生命周期管理
- ✅ MCP 异常映射
- ✅ `call_tool` timeout
- ✅ 健壮的 result 解析

### Phase 5 不包含
- ❌ `secret://` 引用模式（Phase 6）
- ❌ Session 连接池（Phase 6，见下文）
- ❌ Multi-Agent（Future）

---

## 13. Phase 6 预告：Production-Ready 连接池

Phase 5 的 per-call session 模式适用于开发测试，但**生产环境高频调用场景**需要连接池优化。

**Phase 6 目标**：
- 连接复用（避免每次 tool call 重建连接）
- 并发限流（防止打爆 MCP server）
- TTL + 自动回收（防止连接泄漏）
- 故障隔离（单个 session 挂了不影响其他）

详见：`/docs/superpowers/specs/2026-04-09-agent-system-phase6-mcp-connection-pool.md`
