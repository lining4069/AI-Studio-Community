# Agent System 架构设计详解

**日期**: 2026-04-08
**版本**: v1.0
**Phase**: Phase 1-4 完整实现

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
│  │  Tool    │  │   Tool   │  │  (Tavily)│  │ (External)   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Repository Layer (DB Access)                 │
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
| `tool_name` | VARCHAR(50) | 工具名：`calculator`/`datetime`/`websearch` |
| `tool_config` | JSONB | 工具配置（如 `{"api_key": "..."}`） |
| `enabled` | BOOLEAN | 是否启用 |
| **UQ** | `(config_id, tool_name)` | 防止重复添加同一工具 |

#### `agent_mcp_servers` - MCP 服务器配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(64) PK | UUID |
| `user_id` | INTEGER FK→user.id | 所有者 |
| `name` | VARCHAR(100) | 服务器名称 |
| `url` | VARCHAR(500) | MCP 服务器地址 |
| `headers` | JSONB | 请求头（如 `{"Authorization": "Bearer ..."}`） |
| `transport` | VARCHAR(20) | 传输协议：`streamable_http`（默认）或 `sse` |
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
| `config_snapshot` | JSONB | **执行时配置快照**（Phase 4 新增） |

---

## 3. 项目文件结构

```
app/
├── modules/
│   └── agent/                          # Agent 业务模块
│       ├── __init__.py                 # 导出主要类
│       ├── models.py                   # ORM 模型（Session, Run, Message, Step, Config...）
│       ├── schema.py                   # Pydantic request/response schemas
│       ├── repository.py               # 数据库访问层
│       ├── service.py                   # 业务逻辑层
│       ├── router.py                   # FastAPI 路由
│       ├── domain.py                   # 领域对象（DomainConfig, ToolConfigItem...）
│       ├── agent_factory.py            # Agent 实例工厂
│       ├── config_loader.py            # DB→DomainConfig 转换器
│       ├── tool_builder.py             # DomainConfig→list[Tool] 构建器
│       └── tools/
│           └── websearch.py            # WebSearchTool 实现
│
├── services/
│   └── agent/                          # Agent 执行引擎
│       ├── __init__.py
│       ├── core.py                     # Step, AgentState, AgentEvent 数据结构
│       ├── simple_agent.py             # SimpleAgent（单轮执行）
│       ├── react_agent.py              # ReactAgent（多轮推理）
│       ├── prompt_builder.py           # LLM 消息构建
│       ├── factories.py                # create_agent_tools, create_local_tools
│       └── tools/
│           ├── base.py                 # Tool ABC 抽象类
│           ├── spec.py                  # ToolSpec 标准化描述
│           ├── registry.py              # Tool 注册表
│           ├── adapters.py             # LangChain→Tool 适配器
│           ├── langchain_adapter.py    # MCP LangChain 适配
│           └── implementations/
│               ├── calculator_tool.py  # 计算器工具
│               ├── datetime_tool.py     # 日期时间工具
│               └── rag_tool.py         # RAG 检索工具
│
└── dependencies/
    └── infras.py                       # DB session 依赖注入
```

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
│   └── POST   /mcp-servers/{id}/test         # 连接测试
│
└── builtin-tools
    └── GET    /builtin-tools                   # 获取所有内置工具
```

### 4.2 核心 API 详解

#### `POST /v1/agent/sessions/{id}/runs` - 发起 Agent 执行

**Request:**
```json
{
  "input": "帮我查一下今天北京的天气",
  "stream": true
}
```

**Response (stream=true):**
```
event: step_start
data: {"step_id": "xxx", "step_index": 0, "type": "llm_decision", ...}

event: tool_call
data: {"tool": "websearch", "arguments": {"query": "北京天气"}, ...}

event: step_end
data: {"step_id": "xxx", "status": "success", "output": {...}, ...}

event: run_end
data: {"status": "success", "output": "今天北京天气晴朗...", ...}
```

#### `GET /v1/agent/configs/{id}/resolved-tools` - 预览实际加载的工具

用于调试，查看某个 Config 实际会加载哪些工具。

**Response:**
```json
{
  "data": {
    "tools": [
      {"name": "calculator", "description": "数学计算工具", "enabled": true},
      {"name": "websearch", "description": "网络搜索 (Tavily)", "enabled": true}
    ],
    "warnings": ["mcp:github load failed: connection timeout"]
  }
}
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
│ 3. 创建 LLM 实例 (_get_llm_for_session)      │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 4. Phase 4: 加载 AgentConfig                  │
│    - session.config_id → AgentConfigLoader    │
│    - DB → DomainConfig                       │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 5. 构建 Tools (ToolBuilder.build)            │
│    - 内置工具: calculator, datetime, websearch│
│    - MCP 工具: langchain-mcp-adapters         │
│    - RAG 工具: knowledge base retrieval       │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 6. 选择 Agent 类型 (AgentFactory)            │
│    - config.agent_type = "simple" → SimpleAgent
│    - config.agent_type = "react" → ReactAgent │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 7. 创建 AgentRun (立即创建，status=running)    │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 8. 保存 config_snapshot (执行快照)            │
│    - 存入 AgentRun.config_snapshot            │
│    - 确保后续 resume 使用相同配置              │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 9. SSE 流式执行 (agent.stream_run)            │
│    - step_start → INSERT step (status=running)│
│    - step_end → UPDATE step (status/output)   │
│    - RUN_END → 持久化 assistant message       │
│               生成 summary                    │
│               更新 run status                 │
└──────────────────────────────────────────────┘
     │
     ▼
返回 SSE 流
```

### 5.2 Resume 流程（resume_agent）

```
用户发起 resume 请求
     │
     ▼
┌──────────────────────────────────────────────┐
│ 1. 获取原始 Run + 验证 ownership              │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 2. 获取成功的 steps (status=success)          │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 3. 重建状态                                  │
│    - messages: 历史消息 + successful outputs  │
│    - tool_results: 成功 tool 的输出          │
│    - summary: Session summary                │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 4. 从 config_snapshot 加载 DomainConfig       │
│    - 使用 Run 执行时的快照，而非当前 Config    │
│    - 保证可复现性                            │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 5. 构建 Tools + 选择 Agent (同 stream_agent) │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 6. 创建新 Run (原 Run 标记为 interrupted)     │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 7. 从 last_step_index + 1 继续执行           │
└──────────────────────────────────────────────┘
```

### 5.3 Config 管理流程

```
用户创建 Config
     │
     ▼
┌──────────────────────────────────────────────┐
│ POST /configs                                │
│ - name, agent_type, max_loop, system_prompt │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 添加内置工具                                  │
│ POST /configs/{id}/tools                    │
│ - tool_name: "calculator" | "datetime" | "websearch"
│ - tool_config: {"api_key": "..."}           │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 创建 MCP 服务器                               │
│ POST /mcp-servers                           │
│ - name, url, headers, transport              │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 关联 MCP 服务器到 Config                       │
│ POST /configs/{id}/mcp-servers              │
│ - mcp_server_id                             │
└──────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│ 绑定 Session 到 Config                        │
│ PATCH /sessions/{id}/config                  │
│ - config_id                                  │
└──────────────────────────────────────────────┘
```

---

## 6. 工具系统

### 6.1 工具架构

```
                    ┌─────────────────┐
                    │    Tool ABC     │  (app/services/agent/tools/base.py)
                    │   - name        │
                    │   - description │
                    │   - input_schema│
                    │   + run()       │
                    │   + to_spec()   │
                    └─────────────────┘
                           ▲
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────────────┐ ┌──────────────┐ ┌───────────────┐
    │CalculatorTool│ │ DateTimeTool│ │WebSearchTool │
    └──────────────┘ └──────────────┘ └───────────────┘
           │               │               │
           └───────────────┴───────────────┘
                           │
                    ┌──────┴──────┐
                    │   ToolBuilder  │
                    │ (modules/agent)│
                    └───────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ Built-in    │  │ MCP Tools   │  │ RAG Tool    │
    │ (直接实例化) │  │(langchain) │  │             │
    └─────────────┘  └─────────────┘  └─────────────┘
```

### 6.2 内置工具注册

内置工具通过 `ToolBuilder._build_builtin()` 方法注册：

```python
def _build_builtin(self, tool_cfg: ToolConfigItem) -> Tool | None:
    match tool_cfg.tool_name:
        case "calculator":
            return _CalculatorToolWrapper()
        case "datetime":
            return _DateTimeToolWrapper()
        case "websearch":
            api_key = tool_cfg.tool_config.get("api_key")
            return _WebSearchToolWrapper(api_key=api_key, ...)
```

**内置工具列表：**

| 工具名 | 说明 | 输入 |
|--------|------|------|
| `calculator` | 数学表达式计算 | `{"expression": "1+2*3"}` |
| `datetime` | 获取当前日期时间 | `{}` |
| `websearch` | Tavily 网络搜索 | `{"query": "关键词"}` |

### 6.3 WebSearchTool 实现

```python
class _WebSearchToolWrapper(Tool):
    name = "websearch"
    description = "网络搜索 (Tavily)"

    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    async def run(self, input: dict) -> dict:
        query = input.get("query")
        if not query:
            return {"error": "query is required"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": self.search_depth,
                }
            )
            return {
                "answer": result.get("answer"),
                "results": result.get("results", [])[:5]
            }
```

**特点：**
- 使用 `httpx` 异步 HTTP
- **30 秒超时**保护，防止悬挂
- API Key 通过 `tool_config` 传入

### 6.4 MCP 外部工具

MCP 工具通过 `langchain-mcp-adapters` 加载：

```python
async def _build_mcp(self, mcp_cfg: MCPConfigItem) -> list[Tool]:
    from langchain_mcp_adapters import load_mcp_tools
    from app.services.agent.tools.adapters import to_mcp_tools

    connection = {
        "url": mcp_cfg.url,
        "headers": mcp_cfg.headers or {},
        "transport": mcp_cfg.transport,  # "streamable_http" or "sse"
    }

    lc_tools = await load_mcp_tools(
        connection=connection,
        server_name=mcp_cfg.name,
        tool_name_prefix=True,
    )

    # 转换为我们的 Tool ABC
    return to_mcp_tools(lc_tools)
```

**MCP 工具加载流程：**

```
1. AgentMCPServer (DB) 存储连接信息
       │
       ▼
2. AgentConfigMCP 关联 Config → MCP Server
       │
       ▼
3. ToolBuilder._build_mcp() 使用 langchain-mcp-adapters
   load_mcp_tools(connection=connection, ...)
       │
       ▼
4. to_mcp_tools() 适配为 Tool ABC 接口
       │
       ▼
5. 返回 list[Tool] 给 Agent
```

**错误隔离：** 单个 MCP 服务器加载失败不影响其他工具，错误记录到 `warnings` 列表。

---

## 7. 配置系统

### 7.1 DomainConfig 领域对象

```python
@dataclass
class DomainConfig:
    """与 ORM 解耦的领域对象"""
    id: str
    user_id: int
    name: str
    agent_type: str      # "simple" | "react"
    max_loop: int
    system_prompt: str | None
    llm_model_id: str | None
    tools: list[ToolConfigItem]      # 内置工具配置
    mcp_servers: list[MCPConfigItem]  # MCP 服务器配置
    kbs: list[KBConfigItem]          # 知识库配置
```

### 7.2 配置加载器

```python
class AgentConfigLoader:
    """DB ORM → DomainConfig"""

    async def load(self, config_id: str, user_id: int) -> DomainConfig | None:
        # 1. 查询 AgentConfig + 预加载 relations
        # 2. 验证 ownership
        # 3. 转换为 DomainConfig
        return DomainConfig(...)
```

### 7.3 工具构建器

```python
class ToolBuilder:
    """DomainConfig → list[Tool]"""

    async def build(self, config: DomainConfig | None) -> tuple[list[Tool], list[str]]:
        # 1. 遍历 config.tools → _build_builtin()
        # 2. 遍历 config.mcp_servers → _build_mcp()
        # 3. 遍历 config.kbs → _build_rag()
        # 返回 (tools, warnings)
```

### 7.4 Config 快照机制

```
┌─────────────────────────────────────────────────────────────┐
│                    Config 快照流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  stream_agent() 执行时:                                     │
│                                                             │
│  1. session.config_id → AgentConfigLoader.load()            │
│                     → DomainConfig (当前配置)                │
│                                                             │
│  2. 创建 AgentRun                                           │
│                                                             │
│  3. domain_config.to_snapshot() → JSON                      │
│     存入 AgentRun.config_snapshot                            │
│                                                             │
│  4. Agent 执行...                                           │
│                                                             │
│  5. 用户修改了 AgentConfig (不影响该 Run)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Resume 恢复流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  resume_agent() 执行时:                                      │
│                                                             │
│  1. original_run.config_snapshot → DomainConfig.from_snapshot()
│     使用历史快照，而非当前配置                                │
│                                                             │
│  2. 重建状态，重头执行                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. AgentFactory 工厂模式

### 8.1 create_agent 函数

```python
def create_agent(
    agent_type: str,           # "simple" 或 "react"
    tools: list[Tool],         # 已构建的工具列表
    llm: LLMProvider,          # LLM 提供者
    run_id: str,               # 追踪 ID
    config: DomainConfig | None = None,
) -> SimpleAgent | ReactAgent:
    """根据 agent_type 创建 Agent 实例"""

    max_loop = config.max_loop if config else 5
    system_prompt = config.system_prompt if config else None

    if agent_type == "react":
        return ReactAgent(
            llm=llm, tools=tools,
            max_loop=max_loop,
            system_prompt=system_prompt,
            run_id=run_id,
        )

    return SimpleAgent(
        llm=llm, tools=tools,
        system_prompt=system_prompt,
        run_id=run_id,
    )
```

### 8.2 为什么不用 Agent ABC？

当前只有 2 个 Agent 实现（SimpleAgent, ReactAgent），抽象出 ABC 收益有限。未来扩展到 3+ 个时可考虑添加。

---

## 9. SSE 事件协议

### 9.1 事件类型

```python
class AgentEventType(StrEnum):
    STEP_START = "step_start"      # 步骤开始
    STEP_END = "step_end"          # 步骤结束
    CONTENT = "content"             # 内容输出
    TOOL_CALL = "tool_call"        # 工具调用
    TOOL_RESULT = "tool_result"    # 工具结果
    RUN_END = "run_end"            # 运行结束
    ERROR = "error"                # 错误
    THOUGHT = "thought"           # 思考（ReactAgent）
    OBSERVATION = "observation"    # 观察（ReactAgent）
```

### 9.2 SSE 事件格式

```json
event: step_start
data: {"step_id": "xxx", "run_id": "yyy", "step_index": 0, "type": "llm_decision", "name": null, "status": "running"}

event: tool_call
data: {"step_id": "xxx", "tool": "websearch", "arguments": {"query": "..."}}

event: step_end
data: {"step_id": "xxx", "status": "success", "output": {...}, "latency_ms": 1234}

event: run_end
data: {"status": "success", "output": "最终回答内容", "steps_count": 3}
```

---

## 10. 用户操作流程总结

### 10.1 完整使用流程

```
1. 创建 MCP 服务器 (可选)
   POST /v1/agent/mcp-servers
   → 获得 mcp_server_id

2. 创建 Agent Config
   POST /v1/agent/configs
   → 获得 config_id

3. 添加内置工具
   POST /v1/agent/configs/{config_id}/tools
   {"tool_name": "calculator", "tool_config": {}}
   {"tool_name": "websearch", "tool_config": {"api_key": "..."}}

4. 关联 MCP 服务器 (可选)
   POST /v1/agent/configs/{config_id}/mcp-servers
   {"mcp_server_id": "xxx"}

5. 创建 Session 并绑定 Config
   POST /v1/agent/sessions
   {"config_id": "xxx"}
   → 获得 session_id

6. 发起执行
   POST /v1/agent/sessions/{session_id}/runs
   {"input": "计算 1+2*3", "stream": true}
   → SSE 流

7. 查看执行详情
   GET /v1/agent/runs/{run_id}
   GET /v1/agent/runs/{run_id}/steps
```

### 10.2 调试工具加载

```
GET /v1/agent/configs/{config_id}/resolved-tools
→ 返回实际会加载的工具列表 + warnings
```

---

## 11. Phase 边界

### Phase 1-4 已实现

- ✅ Session 管理
- ✅ SimpleAgent 单轮执行
- ✅ SSE 流式输出
- ✅ Step 持久化 + Resume
- ✅ MCP Server CRUD
- ✅ AgentConfig 配置模板
- ✅ 内置工具注册 (calculator, datetime, websearch)
- ✅ MCP 外部工具加载
- ✅ Config 快照机制

### Phase 5 (未实现)

- ❌ `secret://` 引用模式和 `user_secrets` 表
- ❌ Tool API key 加密存储
- ❌ Multi-Agent 协作
- ❌ Assistant 分享/市场

---

## 12. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Config 快照位置 | `AgentRun.config_snapshot` | Run 是执行单元，Session 是容器 |
| MCP 错误处理 | 单个失败不影响整体 | 微服务隔离原则 |
| 工具类型 | ABC 抽象 + 具体实现 | 统一接口，灵活扩展 |
| API Key 管理 | 直接存 JSONB | Phase 4 范围，Phase 5 再加密 |
