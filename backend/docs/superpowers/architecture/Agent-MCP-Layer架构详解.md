# Agent MCP Layer 架构详解

**日期**: 2026-04-09
**版本**: v1.2
**Phase**: Phase 5 完整实现（MCP Layer 独立化）

---

## 1. 整体架构总览

### 1.1 三层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Runtime Layer                          │
│         SimpleAgent / ReactAgent — 调用 tool.run()                │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Tool Layer                               │
│                                                                  │
│  ┌──────────────────────┐     ┌────────────────────────────────┐ │
│  │   ToolBuilder       │     │    MCPToolAdapter (Agent层)    │ │
│  │   协调者：构建工具   │────▶│  双重职责：接入 + 数据转化       │ │
│  └──────────────────────┘     └────────────────────────────────┘ │
│                  │                            │                    │
│                  │              ┌─────────────┘                    │
│                  ▼              ▼                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐  │
│  │  BuiltinMCPTool (内置)  │  │  MCPProvider (MCP Layer)    │  │
│  │  直接实现 Tool.run()     │  │  接口：list_tools/call_tool  │  │
│  └─────────────────────────┘  └─────────────────────────────┘  │
│                                                                  │
│  BuiltinMCPRegistry                                               │
│  (app/modules/agent/tools/builtin_mcp_registry.py)              │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Infrastructure Layer                     │
│                   app/modules/agent/mcp/                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              MCPProvider (ABC 接口)                       │    │
│  │         list_tools() / call_tool() / close()            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              △                                   │
│                              │ implements                         │
│  ┌───────────────────────────┴─────────────────────────────┐    │
│  │           NativeMCPProvider (原生 SDK 实现)              │    │
│  │  ├── session.py — create_session() 三种传输协议         │    │
│  │  │     stdio / sse / streamable_http                    │    │
│  │  └── tool.py — MCPToolConfig 数据结构                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  exceptions.py — MCP 异常体系                            │    │
│  │  MCPConnectionError / MCPProtocolError / MCPToolExecutionError │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流向总图

```
用户请求 "计算 1+2*3"
     │
     ▼
AgentRuntime.stream_run()
     │
     ▼
ToolBuilder.build(config)
     │
     ├── DomainConfig.tools ──→ _build_builtin()
     │                                    │
     │                                    ▼
     │                          BuiltinMCPTool (Tool)
     │                                    │
     ├── DomainConfig.mcp_servers ──→ _build_mcp()
     │                                    │
     │                                    ▼
     │                          create_mcp_provider()
     │                                    │
     │                                    ▼
     │                          NativeMCPProvider.list_tools()
     │                                    │
     │                                    ▼
     │                          MCPToolAdapter (Tool)
     │
     ▼
AgentRuntime: for tool in tools: tool.run(input)
     │
     ├── BuiltinMCPTool.run() ──→ handler (Python 函数)
     │                                    │
     │                                    ▼
     │                             返回 {"result": 7.0}
     │
     └── MCPToolAdapter.run() ──→ NativeMCPProvider.call_tool()
                                        │
                                        ▼
                                   create_session()
                                        │
                                        ▼
                                   MCP Server (stdio/sse/http)
                                        │
                                        ▼
                                   返回 CallToolResult
                                        │
                                        ▼
                                   _parse_result() ──→ {"result": "..."}
```

---

## 2. 文件结构

```
app/modules/agent/
│
├── mcp/                                    # MCP Infrastructure Layer（独立基础设施）
│   ├── __init__.py                        # 导出：MCPProvider, create_mcp_provider,
│   │                                       #            MCPToolConfig, 异常类
│   ├── provider.py                         # ABC 接口定义
│   │                                       #   ├── MCPProvider (ABC)
│   │                                       #   └── MCPToolDefinition (dataclass)
│   ├── native_provider.py                  # 原生 SDK 实现
│   │                                       #   ├── NativeMCPProvider (implements MCPProvider)
│   │                                       #   └── create_mcp_provider() 工厂函数
│   ├── session.py                          # MCP 连接管理（三协议）
│   │                                       #   create_session() — 上下文管理器
│   ├── tool.py                            # 配置数据类
│   │                                       #   MCPToolConfig (dataclass)
│   └── exceptions.py                       # 异常体系
│                                           #   MCPError / MCPConnectionError /
│                                           #   MCPProtocolError / MCPToolExecutionError /
│                                           #   MCPValidationError
│
├── tools/                                 # Agent Tool Layer（内置工具）
│   ├── __init__.py                         # 导入 builtin_mcp_specs 触发注册
│   ├── base.py                           # Tool ABC 定义
│   │                                       #   Tool.run() / to_spec()
│   ├── spec.py                            # ToolSpec 标准化描述
│   ├── builtin_mcp_registry.py             # 内置工具注册表
│   │                                       #   BuiltinMCPRegistry (单例)
│   │                                       #   BuiltinMCPTool (implements Tool)
│   ├── builtin_mcp_specs.py               # 内置工具规格定义
│   │                                       #   calculator / datetime / rag_retrieval
│   ├── calculator.py                       # （已废弃，归入 builtin_mcp_specs）
│   ├── datetime.py                         # （已废弃，归入 builtin_mcp_specs）
│   ├── rag_tool.py                         # RAGRetrievalTool (implements Tool)
│   └── ...
│
├── tool_builder.py                         # Tool 构建协调者
│                                           #   _build_builtin() / _build_mcp() / _build_rag()
│                                           #   MCPToolAdapter (Agent 层适配器)
│
├── domain.py                              # Agent 领域对象
│                                           #   MCPConfigItem / ToolConfigItem / DomainConfig
│
└── ...
```

---

## 3. MCP Infrastructure Layer 详解

### 3.1 定位与职责

MCP Layer 是**独立的基础设施层**，不引用 Agent 系统任何类（如 `Tool`、`DomainConfig`、`AgentRuntime`）。其唯一职责是：**封装 MCP 协议与 Agent 系统无关的连接和调用逻辑。**

### 3.2 接口契约：`MCPProvider` ABC

```python
# mcp/provider.py

class MCPProvider(ABC):
    """MCP 协议级别的工具发现和执行接口"""

    @property
    def server_name(self) -> str: ...
    @property
    def transport(self) -> str: ...

    async def list_tools(self) -> list[MCPToolDefinition]:
        """发现 MCP 服务器提供的工具"""
        ...

    async def call_tool(self, tool_name: str, input: dict) -> dict:
        """执行 MCP 工具，返回 MCP 协议格式结果"""
        ...

    async def close(self) -> None: ...
```

**关键设计**：
- `list_tools()` / `call_tool()` 是 MCP 协议级别的接口，返回 MCP 原始数据格式
- Agent 层负责将 MCP 格式转化为 Agent 的 `Tool` 接口格式

### 3.3 数据结构：`MCPToolDefinition`

```python
@dataclass
class MCPToolDefinition:
    """MCP 协议级别的工具定义（MCP Schema）"""
    name: str
    description: str
    input_schema: dict  # MCP JSON-RPC schema 格式
```

### 3.4 原生实现：`NativeMCPProvider`

```python
# mcp/native_provider.py

class NativeMCPProvider(MCPProvider):
    """
    MCP Python Native SDK 实现。

    传输协议：stdio / sse / streamable_http
    Session 模式：per-call（每次 call_tool 创建新 session）
    """

    async def list_tools(self) -> list[MCPToolDefinition]:
        async with create_session(transport=..., url=..., ...) as session:
            result = await asyncio.wait_for(
                session.list_tools(), timeout=30.0
            )
        # 转换为 MCPToolDefinition 列表
        return [MCPToolDefinition(name=t.name, ...) for t in result.tools]

    async def call_tool(self, tool_name: str, input: dict) -> dict:
        async with create_session(...) as session:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, input), timeout=self._call_timeout
            )
        return self._parse_result(result)  # text/binary → dict
```

### 3.5 连接管理：`create_session()`

```python
# mcp/session.py — 传输协议统一入口

async with create_session(
    transport="stdio",           # | "sse" | "streamable_http"
    url=...,
    command=...,
    args=...,
    env=...,
    cwd=...,
    headers=...,
) as session:
    await session.initialize()
    yield session
    # context exit → ClientSession.close() → transport cleanup
```

| transport | 底层调用 |
|-----------|---------|
| `stdio` | `StdioServerParameters` + `stdio_client` |
| `sse` | `sse_client` + timeout/sse_read_timeout |
| `streamable_http` | `streamablehttp_client` |

### 3.6 异常体系

```python
# mcp/exceptions.py

MCPError                          # 基类
├── MCPConnectionError            # 连接失败 / 超时
├── MCPProtocolError              # 协议错误 / 握手失败
├── MCPToolExecutionError         # 工具执行失败 / 超时
└── MCPValidationError            # 参数校验失败
```

**异常映射**（session.py）：
```python
except McpError as e:
    if "timeout" in msg or "connection" in msg:
        raise MCPConnectionError(msg) from e
    elif "protocol" in msg or "handshake" in msg:
        raise MCPProtocolError(msg) from e
    else:
        raise MCPConnectionError(msg) from e
```

---

## 4. Agent Tool Layer 详解

### 4.1 Tool ABC — 工具接口契约

```python
# tools/base.py

class Tool(ABC):
    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def run(self, input: dict) -> dict:
        """执行工具，返回 Agent 层标准格式结果"""
        ...
```

**Agent Runtime 只认识 `Tool`**，不区分内置工具还是 MCP 外部工具。

### 4.2 内置工具：`BuiltinMCPTool`

```python
# tools/builtin_mcp_registry.py

class BuiltinMCPTool(Tool):
    """内置工具，直接实现 Tool ABC"""

    async def run(self, input: dict) -> dict:
        handler = self._spec["handler"]  # Python 函数
        return await handler(input, self.rag_service)
```

**注意**：命名中的 "MCP" 是 **Model Context Protocol** 的概念延伸，与外部 MCP 服务器无关。

### 4.3 内置工具注册：`BuiltinMCPRegistry`

```python
# tools/builtin_mcp_specs.py — 触发注册

registry.register("calculator", {
    "name": "calculator",
    "description": "...",
    "input_schema": {...},
    "handler": calculator_handler,  # async def (input, rag_service) -> dict
})

registry.register("datetime", {...})
registry.register("rag_retrieval", {...})
```

**调用链**：
```
ToolBuilder._build_builtin()
     │
     ▼
builtin_registry.create_tool("calculator")
     │
     ▼
BuiltinMCPTool(name, description, input_schema, handler)
     │
     ▼
BuiltinMCPTool.run(input)
     │
     ▼
calculator_handler(input, rag_service=None)
     │
     ▼
{"result": 7.0}
```

---

## 5. MCPToolAdapter — Agent 层适配器

### 5.1 为什么需要适配器

```
Agent Runtime 期望: list[Tool]
     │
     │ tool.run(input) — 统一接口
     ▼
SimpleAgent / ReactAgent
```

MCP Layer 只知道 `MCPProvider` 接口，不知道 `Tool` ABC。适配器负责：
1. **接入**：将 `MCPProvider.call_tool()` 转化为 `Tool.run()` 格式
2. **数据转化**：`MCPToolDefinition` → `Tool` 属性（当前直通）

### 5.2 实现

```python
# tool_builder.py 内

class MCPToolAdapter(Tool):
    """
    MCP Provider → Tool ABC 适配器。

    Agent 层唯一知道 MCP 的地方。
    MCP Layer 完全不知道此适配器的存在。
    """

    def __init__(self, provider: MCPProvider, tool_def: MCPToolDefinition):
        self._provider = provider
        self.name = tool_def.name
        self.description = tool_def.description
        self.input_schema = tool_def.input_schema

    async def run(self, input: dict) -> dict:
        """执行 MCP 工具"""
        result = await self._provider.call_tool(self.name, input)
        return self._adapt_output(result)  # 当前直通，可扩展映射

    def _adapt_output(self, mcp_result: dict) -> dict:
        """MCP Schema → Agent Schema（Phase 5 直通）"""
        return mcp_result
```

### 5.3 数据流

```
Agent Runtime
    │
    │ tool.run({"expression": "1+2*3"})
    │
    ▼
MCPToolAdapter.run()
    │
    │ _provider = NativeMCPProvider
    │
    ▼
NativeMCPProvider.call_tool("calculator", {"expression": "1+2*3"})
    │
    │ 内部：create_session() → session.call_tool() → _parse_result()
    │
    ▼
{"result": 7.0}  ← Agent 层标准格式
```

---

## 6. 完整调用链汇总

### 6.1 工具发现（build 阶段）

```
ToolBuilder.build(config)
     │
     ├── config.tools[i].enabled?
     │    │
     │    └── _build_builtin()
     │              builtin_registry.create_tool(name)
     │                        │
     │                        ▼
     │              BuiltinMCPTool(Tool) ← 直接实现
     │
     └── config.mcp_servers[i].enabled?
          │
          └── _build_mcp()
                    │
                    ▼
            create_mcp_provider(transport, url, command, ...)
                    │
                    ▼
            NativeMCPProvider.list_tools()
                    │
                    ▼
            list[MCPToolDefinition]
                    │
                    ▼
            [MCPToolAdapter(provider, def) for def in tool_defs]
                    │
                    ▼
            list[Tool] → Agent Runtime
```

### 6.2 工具执行（run 阶段）

```
Agent Runtime: tool.run(input)
     │
     ├── BuiltinMCPTool.run()
     │         │
     │         ▼
     │    calculator_handler(input, rag_service)
     │         │
     │         ▼
     │    {"result": ...}
     │
     └── MCPToolAdapter.run()
              │
              ▼
         NativeMCPProvider.call_tool(tool_name, input)
              │
              ▼
         create_session() → session.call_tool()
              │
              ▼
         _parse_result() → {"result": ...}
```

---

## 7. 关键设计决策

### 7.1 为什么 MCP Layer 不继承 Tool ABC？

| 设计 | 原因 |
|------|------|
| MCP Layer 不知道 Tool ABC | **独立可发布**：未来可作为独立 PyPI 包 (`pip install mcp-core`)，被任何 Agent 系统使用 |
| 适配器放在 Agent 层 | **接入是系统特有的**：如何将 MCP 工具接入到自己的工具系统，是 Agent 系统的问题，不是 MCP 协议的问题 |
| `create_mcp_provider()` 工厂函数 | **解耦**：Agent 层不直接引用 `NativeMCPProvider`，只引用接口，未来可替换为 `MockMCPProvider` 等 |

### 7.2 为什么 Per-Call Session？

每次 `call_tool` 创建新 session：
- **实现简单**：无状态复用，无需连接池
- **资源安全**：context exit 自动清理，不会泄露
- **Phase 6 前够用**：连接池在 Phase 6 实现

### 7.3 为什么内置工具不经过 MCP Layer？

内置工具（calculator/datetime）是 **Python 函数**，不需要 MCP 协议：
- 它们的 `handler` 是直接可调用的 Python 函数
- 它们不需要 `session` / `list_tools()` / `call_tool()`
- 经过 MCP Layer 会引入不必要的复杂度

---

## 8. Phase 6-8 对当前架构的影响

| Phase | 改动点 | 对当前架构的影响 |
|-------|--------|----------------|
| Phase 6 | Connection Pool | `create_session()` 改为从 Pool 获取 session，接口不变 |
| Phase 6 | Managed Sessions | `NativeMCPProvider` 改为持有长连接 session，接口不变 |
| Phase 7 | CircuitBreaker | 在 `MCPToolAdapter.run()` 层添加装饰器，接口不变 |
| Phase 7 | Retry | 在 `NativeMCPProvider.call_tool()` 层添加重试逻辑，接口不变 |
| Phase 8 | Adaptive LB | 在 `ToolBuilder._build_mcp()` 层选择 Provider 实现，接口不变 |

**结论**：当前分层架构使 Phase 6-8 的增强点都在**实现层**做，上层接口（`MCPProvider` / `Tool`）完全稳定。

---

## 9. Q&A — 面试 / 汇报视角

---

### Q1: 你们的 MCP 工具接入是如何设计的？

**A**: 我们采用了**适配器模式**，将 MCP 基础设施层与 Agent 系统完全解耦。

整个系统分为三层：
- **MCP Infrastructure Layer**（`app/modules/agent/mcp/`）：纯基础设施，定义 `MCPProvider` 接口，不引用任何 Agent 特有类（MCP SDK 的封装）
- **Agent Tool Layer**（`tool_builder.py`）：负责将 MCP Provider 适配到 `Tool ABC`，也负责内置工具的注册和构建
- **Agent Runtime**（`SimpleAgent` / `ReactAgent`）：只认识 `Tool` 接口，不知道任何 MCP 细节

核心接口是 `MCPProvider` ABC，它定义了 `list_tools()` 和 `call_tool()` 两个契约。任何 MCP 实现（如原生 SDK）只要实现这个接口，就能无缝接入我们的 Agent 系统。

---

### Q2: 为什么 MCP Layer 不能继承 Tool ABC？

**A**: 这是**关注点分离**的设计。

`Tool` ABC 是我们 Agent 系统的接口契约，定义了"一个工具应该长什么样"。但 MCP 协议本身并不知道也不关心"Tool"这个概念——它只知道"发现工具"和"执行工具"。

如果让 `NativeMCPProvider` 继承 `Tool`，就意味着：
1. MCP Layer 必须引用我们 Agent 系统的 `Tool` 类
2. MCP Layer 就不再是一个通用基础设施包
3. 任何想用原生 MCP SDK 的外部系统，都必须先引入我们的 `Tool` ABC

所以我们把"知道 Tool 接口"这件事，放在了 Agent 层的适配器里，MCP Layer 完全不知道这件事。

---

### Q3: 内置工具（calculator/datetime）和外部 MCP 工具的接入有什么区别？

**A**: 两者是**完全独立的路径**，最终都实现 `Tool` 接口。

| | 内置工具 | 外部 MCP 工具 |
|---|---|---|
| 实现方式 | `BuiltinMCPTool(Tool)` 直接实现 `run()` | `MCPToolAdapter(Tool)` 包装 `MCPProvider` |
| 调用链 | `run()` → Python handler 函数 | `run()` → `Provider.call_tool()` → MCP SDK |
| 工具来源 | `builtin_mcp_registry.py`（单例） | `NativeMCPProvider`（每个 MCP Server 一个） |
| 与 MCP SDK 关系 | **完全无关** | 通过原生 MCP SDK |

内置工具的命名里有 "MCP" 实际上是一个历史包袱——它原本想表达"这些工具是按 MCP 规范封装的"，但这和连接外部 MCP 服务器完全是两回事。

---

### Q4: 工具发现超时 30s，工具执行超时 10s，是怎么设计的？

**A**: 这是**两级超时保护**。

```
ToolBuilder.build() 阶段：
    │
    └── NativeMCPProvider.list_tools()
              │
              └── asyncio.wait_for(session.list_tools(), timeout=30s)
                   │
                   └── 超时 → MCPConnectionError

ToolBuilder.run() 阶段：
    │
    └── NativeMCPProvider.call_tool()
              │
              └── asyncio.wait_for(session.call_tool(), timeout=10s)
                   │
                   └── 超时 → MCPToolExecutionError
```

设计理由：
- **list_tools 30s**：MCP 服务器冷启动可能很慢（如拉取镜像、初始化模型），给足够长的时间
- **call_tool 10s**：工具执行应该是快速的操作，10s 已经足够大多数场景

Phase 7 会在此基础上增加 **CircuitBreaker**，当某个 MCP Server 的超时率超过阈值时，自动熔断，不再尝试调用。

---

### Q5: 未来 Phase 6 要做 Connection Pool，当前架构能平滑演进吗？

**A**: 可以，这是我们分层架构的核心优势。

当前架构中，所有 MCP 连接管理都在 `mcp/session.py` 的 `create_session()` 函数里。Phase 6 只需要：
1. 新增 `ConnectionPool` 类
2. `create_session()` 改为从 Pool 获取 session
3. `NativeMCPProvider` 不需要任何改动（它只调用 `create_session()`）
4. `MCPProvider` 接口完全稳定

```
当前：
create_session() → 同步创建 session

Phase 6:
create_session() → Pool.get() → Session (with idle reuse)
```

Agent Runtime、ToolBuilder、MCPToolAdapter **零改动**。

---

### Q6: 如果要替换成其他 MCP SDK 实现呢？

**A**: 只需要替换 `NativeMCPProvider` 的实现，`MCPProvider` 接口不变。

例如，如果我们想用 `FasterMCP` SDK：

```python
# mcp/faster_provider.py

class FasterMCPProvider(MCPProvider):
    async def list_tools(self) -> list[MCPToolDefinition]: ...
    async def call_tool(self, tool_name: str, input: dict) -> dict: ...
    async def close(self) -> None: ...
```

Agent 层代码（`tool_builder.py`）只需要：

```python
from app.modules.agent.mcp import MCPProvider

# 替换这一行：
# provider = create_mcp_provider(config)
provider: MCPProvider = FasterMCPProvider(config)  # 符合相同接口
```

这就是接口隔离的力量：**调用方依赖抽象（`MCPProvider`），不依赖实现（`NativeMCPProvider`）**。

---

### Q7: 数据模型上，`MCPConfigItem` 和 `MCPToolConfig` 是什么关系？

**A**: **两个不同层次的数据模型**。

```
MCPConfigItem（Agent Domain 层）
    │ ← Agent 系统内部，用于数据库持久化
    ▼
create_mcp_provider()（MCP Layer 工厂函数）
    │
    ▼
NativeMCPProvider
    │
    ▼
MCPToolConfig（MCP Layer 运行时配置）
    │ ← MCP 协议级别，只包含传输和运行时参数
```

- `MCPConfigItem` 在 `domain.py`，包含 `mcp_server_id`、`user_id` 等 Agent 特有概念
- `MCPToolConfig` 在 `mcp/tool.py`，只有传输配置（`transport`、`url`、`command`、`args` 等），不包含任何 Agent 层概念

它们通过 `ToolBuilder._build_mcp()` 中的参数映射进行转换：

```python
provider = create_mcp_provider(
    transport=mcp_cfg.transport,    # MCPConfigItem → 函数参数
    server_name=mcp_cfg.name,
    url=mcp_cfg.url,
    command=mcp_cfg.command,
    ...
)
```

---

### Q8: 如果 MCP 服务器返回的错误信息不规范，怎么处理？

**A**: 这是 Phase 5 异常映射的一个局限性，我们有明确的改进计划。

当前 `session.py` 的异常映射依赖**字符串匹配**：

```python
if "timeout" in msg.lower() or "connection" in msg.lower():
    raise MCPConnectionError(msg)
elif "protocol" in msg.lower() or "handshake" in msg.lower():
    raise MCPProtocolError(msg)
```

这种方式的缺点是：如果 MCP SDK 异常消息格式变化，分类就会失效。

Phase 7 会改进为**异常码级别**的分类：
- MCP SDK 异常应该有标准错误码
- 我们在 `exceptions.py` 中定义错误码到异常类型的映射表
- 不再依赖字符串匹配

Phase 7 还会增加 `MCPErrorInspector`，对无法分类的异常进行**.unknown 子类**兜底，而不是直接归为 `MCPConnectionError`。

---

### Q9: 适配器的 `_adapt_output` 目前是直通，未来会扩展什么？

**A**: 主要是**Schema 映射**和**结果标准化**。

例如，某些 MCP 服务器返回的格式可能不统一：

```python
# 服务器 A 返回
{"answer": "北京今天晴", "temperature": 25}

# 服务器 B 返回
{"text": "天气：晴，25°C"}
```

未来可以在 `_adapt_output` 中扩展：

```python
def _adapt_output(self, mcp_result: dict) -> dict:
    """
    扩展点：
    1. 字段映射：mcp_result["text"] → mcp_result["answer"]
    2. 格式标准化：统一返回 {"result": "...", "metadata": {...}}
    3. 结果过滤：去除敏感信息
    4. 类型转换：string → structured dict
    """
    # Phase 5：直通
    return mcp_result
```

这个扩展在 Agent 层做，不影响 MCP Layer。

---

### Q10: 这个架构最大的风险是什么？

**A**: 最大的风险是 **MCP SDK 版本耦合**。

当前 `native_provider.py` 直接引用了 MCP SDK 的类型：

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
```

如果 MCP SDK 升级导致 API breaking change，我们需要修改 `native_provider.py` 和 `session.py`。

应对策略：
1. MCP SDK 版本锁定在 `requirements.txt` 中
2. 在 `session.py` 中对 MCP SDK 异常做统一包装，减少扩散点
3. Phase 7 之后可以考虑引入 **Adapter Facade**，进一步封装 SDK 版本差异

另外，当前 `MCPToolDefinition.inputSchema` 的字段名（注意大小写）与 MCP SDK 直接耦合，是系统中唯一明显的硬编码。未来可以抽象为一个转换函数。

---

## 附录：文件索引

| 文件 | 职责 |
|------|------|
| `mcp/__init__.py` | 模块导出 |
| `mcp/provider.py` | `MCPProvider` ABC + `MCPToolDefinition` |
| `mcp/native_provider.py` | `NativeMCPProvider` 实现 + `create_mcp_provider()` |
| `mcp/session.py` | `create_session()` 三协议连接管理 |
| `mcp/tool.py` | `MCPToolConfig` 数据类 |
| `mcp/exceptions.py` | MCP 异常体系 |
| `tool_builder.py` | `ToolBuilder` + `MCPToolAdapter` |
| `tools/base.py` | `Tool` ABC |
| `tools/builtin_mcp_registry.py` | `BuiltinMCPRegistry` + `BuiltinMCPTool` |
| `tools/builtin_mcp_specs.py` | 内置工具规格定义 |
| `domain.py` | `MCPConfigItem` / `ToolConfigItem` / `DomainConfig` |
