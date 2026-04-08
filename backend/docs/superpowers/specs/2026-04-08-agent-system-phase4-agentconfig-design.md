# Agent System Phase 4 — AgentConfig Layer

**日期**: 2026-04-08
**状态**: Final v3（问题修正版）
**Phase**: Phase 4

---

## 与 Draft v2 的关键差异

| # | 问题 | v2 做法 | v3 修正 |
|---|------|---------|---------|
| P0 | `AgentConfigTool` 字段名冲突 | `config` 字段与 relationship 同名 | relationship 改为 `agent_config`，列字段改为 `tool_config` |
| P0 | `config_snapshot` 位置错误 | 放在 `AgentSession` | 移至 `AgentRun`（Run 是执行单元） |
| P0 | MCP 迁移 NOT NULL 无 DEFAULT | 存量数据迁移失败 | 分步迁移 + DEFAULT 策略 |
| P1 | 关联表缺 `UniqueConstraint` | 重复 link 合法 | `AgentConfigTool`、`AgentConfigMCP`、`AgentConfigKB` 均加 UQ |
| P1 | MCP 工具加载无错误隔离 | 单个失败导致全部失败 | 逐个加载 + 收集失败列表 |
| P1 | API 路径前缀不统一 | `/configs`、`/mcp-servers` | 统一 `/v1/agent/` 前缀 |
| P1 | `SecretManager` 依赖未定义表 | 文档模糊 | Phase 4 明确使用环境变量/直接值，`secret://` 模式推迟到 Phase 5 |
| P2 | `WebSearchTool` 无 timeout | 悬挂请求 | 强制 `total=30s` timeout |
| P2 | `DomainConfig` 未定义 | 实现者猜测 | 给出完整 dataclass 定义 |
| P2 | 文件层次混乱 | `factories.py` 在 services 层 | 整理到 `modules/agent/` 统一管理 |

---

## 数据模型

### AgentMCPServer（修正：user_id 是 FK，不是复合 PK）

```python
class AgentMCPServer(Base, TimestampMixin):
    __tablename__ = "agent_mcp_servers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transport: Mapped[str] = mapped_column(String(20), default="streamable_http")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_mcp_server_user_name"),
    )
```

### AgentConfig

```python
class AgentConfig(Base, TimestampMixin):
    __tablename__ = "agent_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    llm_model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(20), default="simple")  # "simple" | "react"
    max_loop: Mapped[int] = mapped_column(Integer, default=5)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    tools: Mapped[list["AgentConfigTool"]] = relationship(back_populates="agent_config", cascade="all, delete-orphan")
    mcp_links: Mapped[list["AgentConfigMCP"]] = relationship(back_populates="agent_config", cascade="all, delete-orphan")
    kb_links: Mapped[list["AgentConfigKB"]] = relationship(back_populates="agent_config", cascade="all, delete-orphan")
```

### AgentConfigTool（修正：字段名冲突 + UQ 约束）

```python
class AgentConfigTool(Base):
    __tablename__ = "agent_config_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # ★ 列字段改名为 tool_config，避免与 relationship 字段 agent_config 冲突
    tool_config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    agent_config: Mapped["AgentConfig"] = relationship(back_populates="tools")

    __table_args__ = (
        # 同一 config 下不允许重复添加同名工具
        UniqueConstraint("config_id", "tool_name", name="uq_config_tool"),
    )
```

### AgentConfigMCP（修正：加 UQ 约束）

```python
class AgentConfigMCP(Base):
    __tablename__ = "agent_config_mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    mcp_server_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_mcp_servers.id", ondelete="CASCADE"), nullable=False
    )

    agent_config: Mapped["AgentConfig"] = relationship(back_populates="mcp_links")
    mcp_server: Mapped["AgentMCPServer"] = relationship()

    __table_args__ = (
        UniqueConstraint("config_id", "mcp_server_id", name="uq_config_mcp"),
    )
```

### AgentConfigKB（修正：加 UQ 约束 + 字段名规范化）

```python
class AgentConfigKB(Base):
    __tablename__ = "agent_config_kbs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kb_config: Mapped[dict] = mapped_column(JSON, default=dict)  # top_k, threshold 等

    agent_config: Mapped["AgentConfig"] = relationship(back_populates="kb_links")

    __table_args__ = (
        UniqueConstraint("config_id", "kb_id", name="uq_config_kb"),
    )
```

### AgentSession（修正：移除 config_snapshot）

```python
class AgentSession(Base, TimestampMixin):
    # ... 现有字段不变 ...

    # 引用 config，但不存快照（快照在 AgentRun 层）
    config_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True
    )
```

### AgentRun（修正：config_snapshot 归属于此）

```python
class AgentRun(Base, TimestampMixin):
    # ... 现有字段 ...

    # ★ 快照在 Run 层，而非 Session 层
    # 原因：Session 是长期会话容器，Run 是单次执行单元
    # 每次 Run 启动时保存当时 config 的快照，确保该次执行可复现
    # 即使用户后续修改 config，历史 Run 的快照不变
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

---

## Domain Config（完整定义）

```python
from dataclasses import dataclass, field

@dataclass
class ToolConfigItem:
    tool_name: str
    tool_config: dict  # websearch: {"api_key": "...", "search_depth": "basic"}
    enabled: bool = True

@dataclass
class MCPConfigItem:
    mcp_server_id: str
    name: str
    url: str
    headers: dict | None
    transport: str

@dataclass
class KBConfigItem:
    kb_id: str
    kb_config: dict  # top_k, threshold 等

@dataclass
class DomainConfig:
    """AgentConfig 的领域对象，与 ORM 解耦，用于业务逻辑层传递。"""
    id: str
    user_id: int
    name: str
    agent_type: str          # "simple" | "react"
    max_loop: int
    system_prompt: str | None
    llm_model_id: str | None
    tools: list[ToolConfigItem] = field(default_factory=list)
    mcp_servers: list[MCPConfigItem] = field(default_factory=list)
    kbs: list[KBConfigItem] = field(default_factory=list)

    def to_snapshot(self) -> dict:
        """序列化为 JSON 快照，存入 AgentRun.config_snapshot。"""
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_snapshot(cls, data: dict) -> "DomainConfig":
        """从 AgentRun.config_snapshot 反序列化，用于历史 Run 复现。"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            name=data["name"],
            agent_type=data["agent_type"],
            max_loop=data["max_loop"],
            system_prompt=data.get("system_prompt"),
            llm_model_id=data.get("llm_model_id"),
            tools=[ToolConfigItem(**t) for t in data.get("tools", [])],
            mcp_servers=[MCPConfigItem(**m) for m in data.get("mcp_servers", [])],
            kbs=[KBConfigItem(**k) for k in data.get("kbs", [])],
        )
```

---

## ToolBuilder（修正：MCP 错误隔离）

```python
class ToolBuilder:
    def __init__(self, rag_service=None):
        self.rag_service = rag_service

    async def build(self, config: DomainConfig | None) -> tuple[list[Tool], list[str]]:
        """
        返回 (tools, warnings)。
        warnings 包含加载失败的工具信息，不抛出异常。
        调用方可将 warnings 记录到日志或返回给前端用于调试。
        """
        tools: list[Tool] = []
        warnings: list[str] = []

        if not config:
            return [], ["No config provided"]

        for tool_cfg in config.tools:
            if not tool_cfg.enabled:
                continue
            try:
                tool = self._build_builtin(tool_cfg)
                if tool:
                    tools.append(tool)
            except Exception as e:
                warnings.append(f"builtin:{tool_cfg.tool_name} load failed: {e}")

        for mcp_cfg in config.mcp_servers:
            try:
                mcp_tools = await self._build_mcp(mcp_cfg)
                tools.extend(mcp_tools)
            except Exception as e:
                # ★ 单个 MCP server 失败不影响其他工具
                warnings.append(f"mcp:{mcp_cfg.name} load failed: {e}")

        if config.kbs and self.rag_service:
            try:
                rag_tool = self._build_rag(config.kbs)
                tools.append(rag_tool)
            except Exception as e:
                warnings.append(f"rag load failed: {e}")

        return tools, warnings

    def _build_builtin(self, tool_cfg: ToolConfigItem) -> Tool | None:
        match tool_cfg.tool_name:
            case "calculator":
                return CalculatorTool()
            case "datetime":
                return DateTimeTool()
            case "websearch":
                api_key = tool_cfg.tool_config.get("api_key")
                if not api_key:
                    raise ValueError("websearch requires api_key in tool_config")
                return WebSearchTool(
                    api_key=api_key,
                    search_depth=tool_cfg.tool_config.get("search_depth", "basic"),
                )
            case _:
                return None
```

**关于 API Key 管理（Phase 4 范围）**：Phase 4 中 `tool_config.api_key` 直接存储在 `agent_config_tools.tool_config` JSONB 列中。`secret://` 引用模式（需要独立的 `user_secrets` 表和 `SecretManager`）推迟到 Phase 5 实现。

---

## WebSearchTool（修正：httpx + timeout）

```python
import httpx

class WebSearchTool(Tool):
    name = "websearch"
    description = "Search the web for current information using Tavily"

    def __init__(self, api_key: str, search_depth: str = "basic"):
        self.api_key = api_key
        self.search_depth = search_depth

    async def run(self, input: dict) -> dict:
        query = input.get("query")
        if not query:
            return {"error": "query is required"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": self.search_depth,
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                return {
                    "answer": result.get("answer"),
                    "results": result.get("results", [])[:5],
                }
        except httpx.TimeoutException:
            return {"error": "Tavily API timeout (30s)"}
        except httpx.HTTPStatusError as e:
            return {"error": f"Tavily API error: {e.response.status_code}"}
```

---

## Service 层：Run 启动时保存快照

```python
class AgentService:
    async def stream_agent(self, session_id: str, user_id: int, user_input: str):
        session = await self.repo.get_session(session_id, user_id)

        # 1. 加载 config（支持 live config 或 None）
        domain_config: DomainConfig | None = None
        if session.config_id:
            domain_config = await self.config_loader.load(session.config_id, user_id)

        # 2. 构建工具
        tools, warnings = await self.tool_builder.build(domain_config) if domain_config else ([], [])
        if warnings:
            logger.warning("Tool load warnings for session %s: %s", session_id, warnings)

        # 3. 创建 Run
        run = await self.repo.create_run(session_id)

        # 4. ★ 保存快照到 AgentRun（在执行开始前）
        if domain_config:
            await self.repo.update_run_snapshot(run.id, domain_config.to_snapshot())

        # 5. 选择 agent 类型
        agent_type = domain_config.agent_type if domain_config else "simple"
        agent = create_agent(agent_type, tools, self.llm, run.id, domain_config)

        # 6. 执行
        async for event in agent.stream(user_input):
            yield event
```

---

## create_agent 函数（替代静态类）

```python
# app/modules/agent/agent_factory.py

def create_agent(
    agent_type: str,
    tools: list[Tool],
    llm: LLMProvider,
    run_id: str,
    config: DomainConfig | None = None,
) -> Agent:
    """
    根据 agent_type 创建 Agent 实例。
    当前支持: "simple"（默认）、"react"。
    """
    max_loop = config.max_loop if config else 5
    system_prompt = config.system_prompt if config else None

    if agent_type == "react":
        return ReactAgent(
            llm=llm,
            tools=tools,
            max_loop=max_loop,
            system_prompt=system_prompt,
            run_id=run_id,
        )

    return SimpleAgent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        run_id=run_id,
    )
```

---

## API 设计（修正：统一路径前缀）

所有 agent 相关 endpoint 使用 `/v1/agent/` 前缀：

**AgentConfig CRUD**

| Endpoint | Method | 说明 |
|----------|--------|------|
| `/v1/agent/configs` | GET | 列表（当前用户） |
| `/v1/agent/configs` | POST | 创建 |
| `/v1/agent/configs/{id}` | GET | 详情 |
| `/v1/agent/configs/{id}` | PUT | 更新 |
| `/v1/agent/configs/{id}` | DELETE | 删除 |
| `/v1/agent/configs/{id}/tools` | GET/POST | 工具列表/添加 |
| `/v1/agent/configs/{id}/tools/{tool_id}` | PUT/DELETE | 更新/删除工具 |
| `/v1/agent/configs/{id}/mcp-servers` | GET/POST | MCP link 列表/添加 |
| `/v1/agent/configs/{id}/mcp-servers/{link_id}` | DELETE | 解除 MCP link |
| `/v1/agent/configs/{id}/resolved-tools` | GET | 调试：查看实际会加载哪些工具 |
| `/v1/agent/builtin-tools` | GET | 所有内置工具及其 schema |

**MCP Server CRUD**

| Endpoint | Method | 说明 |
|----------|--------|------|
| `/v1/agent/mcp-servers` | GET | 列表（当前用户） |
| `/v1/agent/mcp-servers` | POST | 创建 |
| `/v1/agent/mcp-servers/{id}` | GET/PUT/DELETE | CRUD |
| `/v1/agent/mcp-servers/{id}/test` | POST | 连通性测试 |

**Session 绑定**

| Endpoint | Method | 说明 |
|----------|--------|------|
| `/v1/agent/sessions` | POST | 创建 Session，可带 `config_id` |
| `/v1/agent/sessions/{id}` | PATCH | 更新 `config_id` 绑定 |

---

## 数据库迁移（修正：安全迁移存量数据）

```sql
-- Step 1: 新建 agent_configs
CREATE TABLE agent_configs (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    llm_model_id VARCHAR(64),
    agent_type VARCHAR(20) NOT NULL DEFAULT 'simple',
    max_loop INTEGER NOT NULL DEFAULT 5,
    system_prompt TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: 新建 agent_config_tools（★ tool_config 而非 config）
CREATE TABLE agent_config_tools (
    id SERIAL PRIMARY KEY,
    config_id VARCHAR(64) NOT NULL REFERENCES agent_configs(id) ON DELETE CASCADE,
    tool_name VARCHAR(50) NOT NULL,
    tool_config JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT uq_config_tool UNIQUE (config_id, tool_name)
);

-- Step 3: 新建 agent_config_mcp_servers
CREATE TABLE agent_config_mcp_servers (
    id SERIAL PRIMARY KEY,
    config_id VARCHAR(64) NOT NULL REFERENCES agent_configs(id) ON DELETE CASCADE,
    mcp_server_id VARCHAR(64) NOT NULL REFERENCES agent_mcp_servers(id) ON DELETE CASCADE,
    CONSTRAINT uq_config_mcp UNIQUE (config_id, mcp_server_id)
);

-- Step 4: 新建 agent_config_kbs
CREATE TABLE agent_config_kbs (
    id SERIAL PRIMARY KEY,
    config_id VARCHAR(64) NOT NULL REFERENCES agent_configs(id) ON DELETE CASCADE,
    kb_id VARCHAR(64) NOT NULL,
    kb_config JSONB NOT NULL DEFAULT '{}',
    CONSTRAINT uq_config_kb UNIQUE (config_id, kb_id)
);

-- Step 5: agent_sessions 加 config_id（不加 snapshot！）
ALTER TABLE agent_sessions
    ADD COLUMN config_id VARCHAR(64) REFERENCES agent_configs(id) ON DELETE SET NULL;

-- Step 6: agent_runs 加 config_snapshot（★ 快照在 Run 层）
ALTER TABLE agent_runs
    ADD COLUMN config_snapshot JSONB;

-- Step 7: 修复 agent_mcp_servers（分步，避免存量数据迁移失败）
-- 7a. 先加可空列
ALTER TABLE agent_mcp_servers ADD COLUMN user_id INTEGER REFERENCES users(id);
-- 7b. 业务侧填充存量数据（如有）
-- UPDATE agent_mcp_servers SET user_id = <system_user_id> WHERE user_id IS NULL;
-- 7c. 加 NOT NULL 约束（确保存量数据已填充后执行）
ALTER TABLE agent_mcp_servers ALTER COLUMN user_id SET NOT NULL;
-- 7d. 加唯一约束
ALTER TABLE agent_mcp_servers ADD CONSTRAINT uq_mcp_server_user_name UNIQUE (user_id, name);

-- Step 8: 索引
CREATE INDEX idx_agent_configs_user_id ON agent_configs(user_id);
CREATE INDEX idx_agent_config_tools_config_id ON agent_config_tools(config_id);
CREATE INDEX idx_agent_config_mcp_config_id ON agent_config_mcp_servers(config_id);
CREATE INDEX idx_agent_config_kbs_config_id ON agent_config_kbs(config_id);
CREATE INDEX idx_agent_mcp_servers_user_id ON agent_mcp_servers(user_id);
CREATE INDEX idx_agent_sessions_config_id ON agent_sessions(config_id);
```

---

## 文件结构（整理后）

```
app/modules/agent/
├── models.py           # 所有 ORM 模型（含 Phase 4 新增）
├── schemas.py          # Pydantic request/response schema
├── repository.py       # DB 访问层
├── service.py          # 业务逻辑（AgentService、AgentConfigService）
├── router.py           # FastAPI endpoints
├── domain.py           # DomainConfig, ToolConfigItem 等领域对象（纯 Python dataclass）
├── agent_factory.py    # create_agent() 函数
├── config_loader.py    # AgentConfigLoader（DB → DomainConfig）
├── tool_builder.py     # ToolBuilder（DomainConfig → list[Tool]）
└── tools/
    └── websearch.py    # WebSearchTool（Tavily）

app/services/agent/     # 已有文件，不拆散
├── simple_agent.py
├── react_agent.py      # ★ Phase 4 正式接入
├── core.py
└── tools/
    ├── base.py
    ├── registry.py
    ├── calculator.py
    └── datetime_tool.py
```

---

## Phase 4 不包含（明确边界）

- ❌ `secret://` 引用模式和 `user_secrets` 表（推迟 Phase 5）
- ❌ Tool API key 加密存储（Phase 4 直接存 JSONB，前端负责 HTTPS 传输）
- ❌ Multi-Agent 协作
- ❌ Assistant 分享/市场
- ❌ Tool 级别权限模型

---

## 验证清单

1. 创建 `AgentConfig`，添加 `websearch` tool（带 `api_key`）+ 2 个 MCP server + 1 个 KB link
2. 重复添加同名 tool → 期望 409 Conflict（UQ 约束）
3. 重复 link 同一 MCP server → 期望 409 Conflict
4. 创建 Session 绑定 config_id，发起 Run → 验证 `AgentRun.config_snapshot` 有内容，`AgentSession` 无 snapshot 字段
5. 修改 config → 重新 Run → 验证新 Run 快照反映修改；旧 Run 快照不变
6. 某个 MCP server 地址不通 → 验证其他工具正常加载，Run 正常启动，warnings 记录到日志
7. `agent_type="react"` → 验证 ReactAgent 被调用
8. 调用 `/v1/agent/mcp-servers`（带不同 user token）→ 验证用户隔离
9. WebSearchTool 调用时 Tavily 无响应 → 30s 后返回 timeout error，不挂起
10. 调用 `/v1/agent/configs/{id}/resolved-tools` → 返回预期工具列表
