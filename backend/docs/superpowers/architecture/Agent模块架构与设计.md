# Agent System 架构设计详解

**日期**: 2026-04-09
**版本**: v1.1
**Phase**: Phase 1-5 完整实现

---

## 1. 架构概览

### 1.1 系统分层

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (Router)                       │
│  /v1/agent/sessions, /v1/agent/configs, /v1/agent/mcp-servers  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer (Business Logic)              │
│  AgentService: stream_agent, resume_agent, CRUD operations      │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
┌─────────────────────────┐   ┌─────────────────────────────────┐
│   ToolBuilder          │   │      AgentFactory               │
│   DomainConfig → Tools  │   │   agent_type → Simple/React     │
└─────────────────────────┘   └─────────────────────────────────┘
                    │                       │
                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Agent Runtime (SimpleAgent / ReactAgent)       │
│  LLM → Tool? → Execute → LLM (max 1 or N loops)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Tool Layer (Tool ABC)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │Calculator│  │ DateTime │  │WebSearch │  │ MCP Tools    │   │
│  │(builtin) │  │(builtin) │  │(Tavily) │  │ (Native SDK) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                   MCP Layer (Native SDK)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ stdio       │  │ sse          │  │ streamable_http     │  │
│  │ (子进程)    │  │ (SSE)        │  │ (HTTP流式)           │  │
│  └─────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Repository Layer (DB Access)                   │
│  AgentSession, AgentRun, AgentMessage, AgentStep, AgentConfig   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 实现方式 |
|------|----------|
| **配置与执行分离** | `AgentConfig` 存模板，`AgentRun.config_snapshot` 存执行快照 |
| **工具错误隔离** | MCP 工具加载失败不影响内置工具，`warnings` 列表收集 |
| **状态可重建** | SSOT 原则：状态从 `messages + steps` 重建，非 blob 存储 |
| **用户隔离** | 所有操作通过 `user_id` 验证 ownership |
| **Per-Call Session** | 每次工具调用创建临时 MCP Session，执行后立即释放 |
| **原生 SDK** | Phase 5 移除 langchain-mcp-adapters，使用 MCP Python Native SDK |

---

## 2. 数据模型

### 2.1 实体关系图

```
User
  │
  ├── AgentConfig (1:N) ─────────────────┐
  │     │                                │
  │     ├── AgentConfigTool (1:N)        │
  │     ├── AgentConfigMCP (1:N) ──→ AgentMCPServer
  │     └── AgentConfigKB (1:N)          │
  │                                      │
  └── AgentSession (1:N) ─────────────────┤
        │                                 │
        ├── AgentRun (1:N) ───────────────┤
        │     │                           │
        │     └── config_snapshot (JSON)  │
        │                                 │
        ├── AgentMessage (N:1) ────────────┘
        │     │
        │     └── run_id → AgentRun
        │
        └── AgentStep (N:1)
              │
              └── run_id → AgentRun
```

### 2.2 核心表结构

#### `agent_configs` - Agent 配置模板

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(64) PK | UUID |
| `user_id` | INTEGER FK→user.id | 所有者 |
| `name` | VARCHAR(100) | 配置名称 |
| `description` | TEXT | 描述 |
| `llm_model_id` | VARCHAR(64) | 指定 LLM 模型（可选） |
| `agent_type` | VARCHAR(20) | `"simple"` 或 `"react"` |
| `max_loop` | INTEGER | 最大循环次数，默认 5 |
| `system_prompt` | TEXT | 系统提示词 |
| `enabled` | BOOLEAN | 是否启用 |

#### `agent_config_tools` - 内置工具配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 自增 ID |
| `config_id` | VARCHAR(64) FK | 关联 AgentConfig |
| `tool_name` | VARCHAR(50) | 工具名：`calculator`/`datetime`/`websearch`/`rag_retrieval` |
| `tool_config` | JSONB | 工具配置（如 `{"api_key": "..."}`） |
| `enabled` | BOOLEAN | 是否启用 |
| **UQ** | `(config_id, tool_name)` | 防止重复添加同一工具 |

#### `agent_mcp_servers` - MCP 服务器配置（Phase 5 增强）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(64) PK | UUID |
| `user_id` | INTEGER FK→user.id | 所有者 |
| `name` | VARCHAR(100) | 服务器名称 |
| `transport` | VARCHAR(20) | 传输协议：`streamable_http`（默认）/ `sse` / `stdio` |
| **HTTP 传输** | | |
| `url` | VARCHAR(500) | MCP 服务器地址（SSE/HTTP 传输） |
| `headers` | JSONB | 请求头（如 `{"Authorization": "Bearer ..."}`） |
| **stdio 传输** | | |
| `command` | VARCHAR(100) | 启动命令（如 `"uv"`, `"python"`） |
| `args` | JSONB | 命令参数列表 |
| `env` | JSONB | 环境变量 |
| `cwd` | VARCHAR(500) | 工作目录 |
| `enabled` | BOOLEAN | 是否启用 |
| **UQ** | `(user_id, name)` | 防止同一用户重复创建同名服务器 |

#### `agent_config_mcp_servers` - Config 与 MCP 服务器关联

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | SERIAL PK | 自增 ID |
| `config_id` | VARCHAR(64) FK→agent_configs.id | 关联配置 |
| `mcp_server_id` | VARCHAR(64) FK→agent_mcp_servers.id | 关联 MCP 服务器 |
| **UQ** | `(config_id, mcp_server_id)` | 防止重复关联 |

#### `agent_runs` - 单次执行记录

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(64) PK | UUID |
| `session_id` | VARCHAR(64) FK | 所属 Session |
| `status` | VARCHAR(20) | `running`/`success`/`error`/`interrupted` |
| `input` | TEXT | 用户输入 |
| `output` | TEXT | Agent 输出 |
| `error` | TEXT | 错误信息 |
| `last_step_index` | INTEGER | 最后成功 step 索引（用于 resume） |
| `resumable` | BOOLEAN | 是否可恢复 |
| `trace_id` | VARCHAR(64) | 追踪 ID |
| `config_snapshot` | JSONB | **执行时配置快照** |

---

## 3. 项目文件结构

```
app/
├── modules/
│   └── agent/                          # Agent 业务模块
│       ├── __init__.py
│       ├── models.py                   # ORM 模型
│       ├── schema.py                   # Pydantic schemas（Phase 5 增强：stdio 传输验证）
│       ├── repository.py               # 数据库访问层（Phase 5 增强：stdio CRUD）
│       ├── service.py                   # 业务逻辑层（Phase 5：test_mcp_server 超时）
│       ├── router.py                   # FastAPI 路由
│       ├── domain.py                   # 领域对象（Phase 5：MCPConfigItem 增强 stdio 字段）
│       ├── agent_factory.py            # Agent 实例工厂
│       ├── config_loader.py            # DB→DomainConfig 转换器
│       ├── tool_builder.py             # DomainConfig→list[Tool]（Phase 5：原生 SDK + 超时）
│       │
│       ├── mcp/                        # MCP Native SDK 封装（Phase 5 新增）
│       │   ├── __init__.py
│       │   ├── exceptions.py           # MCP 异常层级
│       │   │                            #   MCPError
│       │   │                            #   ├── MCPConnectionError
│       │   │                            #   ├── MCPProtocolError
│       │   │                            #   ├── MCPToolExecutionError
│       │   │                            #   └── MCPValidationError
│       │   ├── session.py              # Session 管理（三种传输协议）
│       │   │                            #   - stdio: StdioServerParameters
│       │   │                            #   - sse: sse_client + timeout
│       │   │                            #   - streamable_http: streamablehttp_client
│       │   │                            #   Per-call session 模式
│       │   └── tool.py                 # MCPTool 运行时
│       │                                #   - asyncio.wait_for(call_tool, timeout=10s)
│       │                                #   - 结果解析（text/binary）
│       │
│       └── tools/                      # 内置 Tool 实现
│           ├── __init__.py             # builtin_mcp_specs 导入触发注册
│           ├── base.py                 # Tool ABC 抽象类
│           ├── spec.py                 # ToolSpec 标准化描述
│           ├── builtin_mcp_registry.py  # 内置 MCP 工具注册表（Phase 5 新增）
│           │                            #   BuiltinMCPRegistry 单例
│           │                            #   BuiltinMCPTool 实现
│           ├── builtin_mcp_specs.py    # 内置工具规格定义（Phase 5 新增）
│           │                            #   calculator / datetime / rag_retrieval
│           ├── calculator.py           # CalculatorTool 实现
│           ├── datetime.py             # DateTimeTool 实现
│           └── rag_tool.py             # RAGRetrievalTool 实现
│
├── services/
│   └── agent/                          # Agent 执行引擎（纯逻辑，无 DB 依赖）
│       ├── __init__.py
│       ├── core.py                     # Step, AgentState, AgentEvent 数据结构
│       ├── simple_agent.py             # SimpleAgent（单轮执行）
│       ├── react_agent.py              # ReactAgent（多轮推理）
│       ├── prompt_builder.py           # LLM 消息构建
│       └── adapters/                   # Tool 接口适配器
│           ├── __init__.py
│           └── openai_adapter.py       # ToolSpec → OpenAI function calling 格式
│
└── dependencies/
    └── infras.py                       # DB session 依赖注入
```

**分层原则：**
- `services/agent/` 是纯执行引擎，**不依赖** `modules/agent/`
- `modules/agent/mcp/` 是 Phase 5 新增的 MCP 原生 SDK 封装层
- `modules/agent/tools/builtin_mcp_*` 是 Phase 5 新增的内置 MCP 工具系统
- Tool 实现（calculator, datetime, rag_tool）在 `modules/agent/tools/`

---

## 4. API 设计

### 4.1 API 路径总览

所有 Agent API 均以 `/v1/agent/` 为前缀。

```
/v1/agent/
├── sessions
│   ├── POST   /sessions                      # 创建 Session
│   ├── GET    /sessions/{id}                 # 获取 Session
│   ├── PATCH  /sessions/{id}/config          # 绑定 Config
│   ├── GET    /sessions/{id}/messages        # 获取消息历史
│   ├── GET    /sessions/{id}/steps            # 获取执行步骤
│   └── POST   /sessions/{id}/runs             # 发起 Run
│
├── runs
│   ├── GET    /runs/{id}                     # 获取 Run 详情
│   ├── GET    /runs/{id}/steps                # 获取 Run 的步骤
│   ├── POST   /runs/{id}/resume               # 恢复中断的 Run
│   └── POST   /runs/{id}/stop                 # 停止 Run
│
├── configs
│   ├── POST   /configs                        # 创建 Config
│   ├── GET    /configs                        # 列表（分页）
│   ├── GET    /configs/{id}                   # 详情
│   ├── PUT    /configs/{id}                   # 更新
│   ├── DELETE /configs/{id}                   # 删除
│   ├── GET    /configs/{id}/tools             # 获取工具列表
│   ├── POST   /configs/{id}/tools             # 添加工具
│   ├── PUT    /configs/{id}/tools/{tool_id}   # 更新工具
│   ├── DELETE /configs/{id}/tools/{tool_id}   # 删除工具
│   ├── GET    /configs/{id}/resolved-tools    # 调试：解析后的工具
│   ├── POST   /configs/{id}/mcp-servers      # 关联 MCP 服务器
│   ├── DELETE /configs/{id}/mcp-servers/{link_id}  # 解除关联
│   ├── POST   /configs/{id}/kbs              # 关联知识库
│   └── DELETE /configs/{id}/kbs/{link_id}    # 解除关联
│
├── mcp-servers
│   ├── POST   /mcp-servers                    # 创建 MCP 服务器
│   ├── GET    /mcp-servers                    # 列表
│   ├── GET    /mcp-servers/{id}               # 详情
│   ├── PUT    /mcp-servers/{id}               # 更新
│   ├── DELETE /mcp-servers/{id}               # 删除
│   └── POST   /mcp-servers/{id}/test         # 连接测试（Phase 5：30s 超时）
│
└── builtin-tools
    └── GET    /builtin-tools                   # 获取所有内置工具
```

### 4.2 MCP Server API（Phase 5 增强）

#### `POST /v1/agent/mcp-servers` - 创建 MCP 服务器（支持 stdio）

**HTTP/SSE 传输：**
```json
{
  "name": "github-mcp",
  "transport": "streamable_http",
  "url": "https://mcp.github.com/sse",
  "headers": {"Authorization": "Bearer xxx"},
  "enabled": true
}
```

**stdio 传输：**
```json
{
  "name": "filesystem-mcp",
  "transport": "stdio",
  "command": "uv",
  "args": ["--directory", "/project", "run", "mcp-server-fs"],
  "env": {"API_KEY": "xxx"},
  "cwd": "/project",
  "enabled": true
}
```

#### `POST /v1/agent/mcp-servers/{id}/test` - 连接测试

Phase 5 增强：使用 `list_tools()` 验证连接，**30s 超时保护**。

**正常响应：**
```json
{"success": true, "message": "Connection successful", "tools_count": 12}
```

**连接超时：**
```json
{"success": false, "message": "Connection timeout after 30s", "tools_count": 0}
```

---

## 5. 业务逻辑流

### 5.1 Agent 执行流程（stream_agent）

```
用户发起请求
     │
     ▼
┌──────────────────────────────────────────────┐
│ 1. 获取 Session + 验证 ownership              │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 2. 加载历史消息 (messages)                   │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 3. 创建 LLM 实例 (_get_llm_for_session)     │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 4. 加载 AgentConfig (Phase 4)                 │
│    - session.config_id → AgentConfigLoader  │
│    - DB → DomainConfig                       │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 5. 构建 Tools (ToolBuilder.build)            │
│    - 内置工具: calculator, datetime,         │
│      rag_retrieval, websearch                │
│    - MCP 工具: Native SDK (Phase 5)          │
│    - RAG 工具: knowledge base retrieval       │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 6. 选择 Agent 类型 (AgentFactory)             │
│    - config.agent_type="simple" → SimpleAgent│
│    - config.agent_type="react" → ReactAgent  │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 7. 创建 AgentRun (status=running)             │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 8. 保存 config_snapshot                      │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 9. SSE 流式执行 (agent.stream_run)           │
│    - step_start → step_end → run_end        │
└──────────────────────────────────────────────┘
     │
     ▼
返回 SSE 流
```

### 5.2 MCP 工具构建流程（Phase 5 Native SDK）

```
ToolBuilder.build() 遍历 config.mcp_servers
     │
     ▼
检查 mcp_cfg.enabled == True?
     │
     ├── False: 跳过
     │
     └── True: _build_mcp(mcp_cfg)
              │
              ▼
         create_session(transport, url, command, args, ...)
              │
              ├── stdio: StdioServerParameters + stdio_client
              ├── sse: sse_client + timeout/sse_read_timeout
              └── streamable_http: streamablehttp_client
              │
              ▼
         asyncio.wait_for(session.list_tools(), timeout=30s)
              │← 超时 → MCPConnectionError("timeout after 30s")
              │
              ▼
         遍历 tools → MCPTool(config, tool_name, description, schema)
              │
              ▼
         返回 list[Tool]
              │
              ▼
build() 返回 (tools, warnings)
```

### 5.3 MCP Session 生命周期（Per-Call 模式）

```
每次 MCPTool.run() 调用：
     │
     ▼
async with create_session(...) as session:
     │
     ▼
session.call_tool(tool_name, input)
     │
     ▼
asyncio.wait_for(call, timeout=10s)
     │
     ├── 超时 → MCPToolExecutionError
     ├── MCPError → 按类型映射
     └── 成功 → 解析 result.content
              │
              ▼
Session context exit → ClientSession.close() → transport cleanup
```

**特点**：
- 每次 `run()` 创建新 Session，无状态复用
- Session 生命周期极短，资源立即释放
- 长连接 MCP 服务器（如 SSE）每次也重新建立连接

---

## 6. 工具系统

### 6.1 工具架构

```
                    ┌─────────────────┐
                    │    Tool ABC     │  (app/modules/agent/tools/base.py)
                    │   - name        │
                    │   - description │
                    │   - input_schema│
                    │   + run()      │
                    │   + to_spec()  │
                    └─────────────────┘
                           ▲
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────────────┐ ┌──────────────┐ ┌───────────────┐
    │CalculatorTool│ │ DateTimeTool│ │ WebSearchTool │
    │  (builtin)   │ │  (builtin)   │ │  (Tavily)    │
    └──────────────┘ └──────────────┘ └───────────────┘
           │               │               │
           └───────────────┴───────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
   ┌──────┴──────┐     ┌───────┴───────┐
   │ Builtin     │     │ MCP Tools    │
   │ Registry    │     │(Native SDK)  │
   │ Phase 5     │     │ Phase 5      │
   └─────────────┘     └──────────────┘
          │
    ┌─────┴─────┐
    │calculator │
    │datetime   │
    │rag_retrieval
    └───────────┘
```

### 6.2 内置工具（Phase 5 内置 MCP 工具）

Phase 5 通过 `builtin_mcp_registry.py` + `builtin_mcp_specs.py` 实现内置 MCP 风格工具。

**内置工具列表：**

| 工具名 | 说明 | 输入 |
|--------|------|------|
| `calculator` | AST 安全数学计算 | `{"expression": "1+2*3"}` |
| `datetime` | 获取当前日期时间 | `{}` |
| `rag_retrieval` | 知识库检索 | `{"query": "关键词"}` |

**工具注册机制：**

`tools/__init__.py` 中 `import builtin_mcp_specs` 触发注册：
```python
# builtin_mcp_specs.py
registry.register("calculator", {
    "name": "calculator",
    "description": "...",
    "input_schema": {...},
    "handler": calculator_handler,
})
```

### 6.3 CalculatorTool 实现（AST 安全计算）

```python
async def calculator_handler(input: dict, rag_service) -> dict:
    expression = input.get("expression", "")

    # AST 安全运算映射（仅支持加减乘除幂取反）
    safe_ops = {
        ast.Add, ast.Sub, ast.Mult, ast.Div,
        ast.Pow, ast.USub,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in safe_ops:
            return safe_ops[type(node.op)](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in safe_ops:
            return safe_ops[type(node.op)](eval_node(node.operand))
        raise ValueError(f"Unsupported: {type(node.op).__name__}")

    try:
        parsed = ast.parse(expression, mode='eval')
        return {"result": eval_node(parsed.body)}
    except Exception as e:
        return {"error": f"Calculation error: {e}"}
```

**安全保证**：使用 `ast.parse` 而非 `eval`，仅允许数学运算，无法执行任意代码。

### 6.4 WebSearchTool 实现

```python
class _WebSearchToolWrapper(Tool):
    name = "websearch"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    async def run(self, input: dict) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.tavily.com/search", json={...})
            return {"answer": result.get("answer"), "results": [...]}
```

### 6.5 MCP 外部工具（Phase 5 Native SDK）

Phase 5 使用 MCP Python Native SDK 替代 langchain-mcp-adapters：

```python
# tool_builder.py
async def _build_mcp(self, mcp_cfg: MCPConfigItem) -> list[Tool]:
    async with create_session(
        transport=mcp_cfg.transport,   # "stdio" | "sse" | "streamable_http"
        url=mcp_cfg.url,                # HTTP/SSE 传输用
        command=mcp_cfg.command,         # stdio 传输用
        args=mcp_cfg.args,               # stdio 传输用
        env=mcp_cfg.env,                 # stdio 传输用
        cwd=mcp_cfg.cwd,                 # stdio 传输用
        headers=mcp_cfg.headers,         # HTTP 传输用
    ) as session:
        try:
            result = await asyncio.wait_for(
                session.list_tools(),
                timeout=30.0,           # 工具发现超时保护
            )
        except asyncio.TimeoutError:
            raise MCPConnectionError(
                f"MCP server {mcp_cfg.name} list_tools() timeout after 30s"
            )

    # 为每个 tool 创建 MCPTool 实例
    for t in result.tools:
        tools.append(MCPTool(
            config=MCPToolConfig(...),
            tool_name=t.name,
            description=t.description or "",
            input_schema=getattr(t, 'inputSchema', {}) or {},
        ))
    return tools
```

**MCPTool.run() 超时保护：**

```python
async def run(self, input: dict) -> dict:
    try:
        async with create_session(...) as session:
            result = await asyncio.wait_for(
                session.call_tool(self._tool_name, input),
                timeout=self._call_timeout,  # 10s
            )
            return self._parse_result(result)
    except asyncio.TimeoutError:
        raise MCPToolExecutionError(f"Tool {self._tool_name} timeout after 10s")
    except MCPConnectionError:
        raise  # 保持原始类型
    except Exception as e:
        raise MCPToolExecutionError(f"Tool {self._tool_name} failed: {e}") from e
```

**MCP 错误隔离：** 单个 MCP 服务器加载失败不影响其他工具，错误记录到 `warnings` 列表。

---

## 7. MCP 异常体系

Phase 5 定义了 MCP 专用异常层级（`mcp/exceptions.py`）：

```
MCPError
├── MCPConnectionError    # 连接失败（超时、拒绝）
├── MCPProtocolError       # 协议错误（握手失败、不支持的方法）
├── MCPToolExecutionError # 工具执行失败（超时、执行异常）
└── MCPValidationError    # 参数校验失败
```

**异常映射（session.py）：**

```python
except McpError as e:
    error_msg = str(e)
    if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
        raise MCPConnectionError(error_msg) from e
    elif "protocol" in error_msg.lower() or "handshake" in error_msg.lower():
        raise MCPProtocolError(error_msg) from e
    else:
        raise MCPConnectionError(error_msg) from e
```

---

## 8. 配置系统

### 8.1 DomainConfig 领域对象

```python
@dataclass
class DomainConfig:
    id: str
    user_id: int
    name: str
    agent_type: str      # "simple" | "react"
    max_loop: int
    system_prompt: str | None
    llm_model_id: str | None
    tools: list[ToolConfigItem]      # 内置工具配置
    mcp_servers: list[MCPConfigItem] # MCP 服务器配置
    kbs: list[KBConfigItem]          # 知识库配置
```

### 8.2 MCPConfigItem（Phase 5 增强）

```python
@dataclass
class MCPConfigItem:
    mcp_server_id: str
    name: str
    transport: str                    # "stdio" | "sse" | "streamable_http"
    url: str | None = None            # HTTP/SSE
    headers: dict | None = None       # HTTP
    command: str | None = None        # stdio
    args: list[str] | None = None     # stdio
    env: dict[str, str] | None = None # stdio
    cwd: str | None = None            # stdio
    enabled: bool = True
```

### 8.3 Config 快照机制

```
stream_agent() 执行时:
  session.config_id → AgentConfigLoader.load() → DomainConfig
  DomainConfig.to_snapshot() → JSON → AgentRun.config_snapshot

resume_agent() 执行时:
  original_run.config_snapshot → DomainConfig.from_snapshot()
  使用历史快照，而非当前配置，保证可复现性
```

---

## 9. AgentFactory 工厂模式

```python
def create_agent(
    agent_type: str,           # "simple" 或 "react"
    tools: list[Tool],        # 已构建的工具列表
    llm: LLMProvider,          # LLM 提供者
    run_id: str,               # 追踪 ID
    config: DomainConfig | None = None,
) -> SimpleAgent | ReactAgent:
    if agent_type == "react":
        return ReactAgent(llm=llm, tools=tools, max_loop=..., ...)
    return SimpleAgent(llm=llm, tools=tools, ...)
```

---

## 10. SSE 事件协议

### 10.1 事件类型

```python
class AgentEventType(StrEnum):
    STEP_START = "step_start"      # 步骤开始
    STEP_END = "step_end"          # 步骤结束
    CONTENT = "content"             # 内容输出
    TOOL_CALL = "tool_call"        # 工具调用
    TOOL_RESULT = "tool_result"   # 工具结果
    RUN_END = "run_end"            # 运行结束
    ERROR = "error"                # 错误
    THOUGHT = "thought"           # 思考（ReactAgent）
    OBSERVATION = "observation"   # 观察（ReactAgent）
```

### 10.2 SSE 事件格式

```
event: step_start
data: {"step_id": "xxx", "run_id": "yyy", "step_index": 0, "type": "llm_decision", ...}

event: tool_call
data: {"step_id": "xxx", "tool": "calculator", "arguments": {"expression": "1+2"}}

event: step_end
data: {"step_id": "xxx", "status": "success", "output": {"result": 3.0}, "latency_ms": 12}

event: run_end
data: {"status": "success", "output": "1+2 = 3", "steps_count": 2}
```

---

## 11. Phase 边界

### Phase 1-5 已实现

- ✅ Session 管理
- ✅ SimpleAgent 单轮执行
- ✅ SSE 流式输出
- ✅ Step 持久化 + Resume
- ✅ MCP Server CRUD（HTTP/SSE/stdio 三种传输）
- ✅ AgentConfig 配置模板
- ✅ 内置工具注册 (calculator, datetime, websearch, rag_retrieval)
- ✅ MCP 外部工具加载（**Native SDK**，Phase 5）
- ✅ Config 快照机制
- ✅ 内置 MCP 工具系统（calculator/datetime/rag_retrieval，Phase 5）

### Phase 6-8 暂未实现（待上线后迭代）

- ❌ Connection Pool + Managed Sessions
- ❌ CircuitBreaker / Retry / LoadShedding
- ❌ Adaptive Concurrency / Health Monitor / Hedging / EWMA LB

---

## 12. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| MCP SDK | Native SDK（原生） | Phase 5 移除 langchain-mcp-adapters，更轻量，传输协议控制更直接 |
| Session 模式 | Per-Call（每次调用创建新 Session） | 实现简单，资源隔离好， Phase 6 前够用 |
| list_tools 超时 | 30s，通过 `asyncio.wait_for` | 防止 MCP Server 冷启动导致 Agent 初始化挂起 |
| call_tool 超时 | 10s，通过 `asyncio.wait_for` | 工具执行超时保护，防止长时间悬挂 |
| stdio 超时 | 未传递 timeout 参数 | MCP SDK stdio client 不支持传输层超时，需 Phase 6+ 实现进程超时 |
| 异常分类 | 字符串匹配 + 异常类型双重判断 | 健壮性一般，Phase 7 将改进为异常码级别分类 |
| Config 快照位置 | `AgentRun.config_snapshot` | Run 是执行单元，Session 是容器 |
| MCP 错误处理 | 单个失败不影响整体 | 微服务隔离原则 |
| 工具类型 | ABC 抽象 + 具体实现 | 统一接口，灵活扩展 |
