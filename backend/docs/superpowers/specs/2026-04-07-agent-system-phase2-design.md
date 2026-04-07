# Agent System Phase 2 Design - Run Observability + Resume

**Date:** 2026-04-07
**Author:** Agent System Design
**Status:** Draft

---

## Context

Phase 1 完成了 Agent System 的核心骨架：
- Session / Message / Step 三层模型
- Tool ABC + Registry
- SimpleAgent (1-loop)
- SSE Streaming
- Summary Memory

**Phase 1 遗留问题：**
- Run 无独立记录，无法 replay/debug
- Steps 关联 Session 而非 Run，replay 依赖 session messages
- 无 resume 能力（服务中断 = 任务丢失）
- SSE 事件缺 step_id，前端无法精确追踪

---

## Phase 2 目标

**聚焦：Run 可观测性 + Resume 能力**

---

## 设计决策

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | Run 粒度 | A: 一次完整 API 请求 | 语义清晰，数据量可控 |
| 2 | Resume 粒度 | B: Step-level Resume | 平衡复杂度 + 可靠性 |
| 3 | Run 创建时机 | A: 请求开始时立即创建 | 支持 resume + 实时可观测性 |
| 4 | Run 与 Message 关系 | B: Run-owned Messages + Session Summary | 自包含，支持多 Agent |
| 5 | ToolSpec | B: 不做 + 接口预留 | MCP 未接入，不锁死 schema |

---

## 数据模型

### 现有模型（不变）

```
agent_sessions
  id, user_id, title, mode, summary
  created_at, updated_at

agent_messages (扩展)
  id, session_id, role, content, metadata
  + run_id      -- 新增: Run 归属
  created_at     -- TimestampMixin

agent_steps (扩展)
  id, session_id, step_index, type, name
  input, output, status, error, latency_ms
  + run_id      -- 新增: Run 关联
  + idempotency_key  -- 可选: 幂等键
  created_at, updated_at  -- TimestampMixin
```

### 新增模型

```python
class AgentRunStatus(StrEnum):
    """Run execution status"""
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class AgentRun(Base, TimestampMixin):
    """
    Agent run - a single execution instance.

    Represents one complete execution of the Agent (one /runs API request).
    """
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Execution type
    type: Mapped[str] = mapped_column(String(20), default="chat")

    # Core state
    status: Mapped[str] = mapped_column(
        String(20), default=AgentRunStatus.RUNNING.value
    )

    # Execution summary
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resume support
    last_step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Note: last_step_index 由 service 层在每个 step 完成后更新
    resumable: Mapped[bool] = mapped_column(default=True)

    # Traceability
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamps (from TimestampMixin)
    # created_at, updated_at
```

### 最终数据层级

```
Session
  └── summary（长期记忆，仅 LLM 摘要）

  └── Runs (agent_runs)
        ├── messages（run_id 归属）
        └── steps（run_id 关联）
```

---

## 数据库变更

### Migration: 添加 agent_runs 表

```sql
CREATE TABLE agent_runs (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    type VARCHAR(20) DEFAULT 'chat',
    status VARCHAR(20) DEFAULT 'running',
    input TEXT NOT NULL,
    output TEXT,
    error TEXT,
    last_step_index INTEGER,
    resumable BOOLEAN DEFAULT TRUE,
    trace_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_agent_runs_session_id ON agent_runs(session_id);
CREATE INDEX ix_agent_runs_status ON agent_runs(status);
```

### Migration: 扩展 agent_messages

```sql
ALTER TABLE agent_messages ADD COLUMN run_id VARCHAR(64);
CREATE INDEX ix_agent_messages_run_id ON agent_messages(run_id);
```

### Migration: 扩展 agent_steps

```sql
ALTER TABLE agent_steps ADD COLUMN run_id VARCHAR(64);
ALTER TABLE agent_steps ADD COLUMN idempotency_key VARCHAR(64);
CREATE INDEX ix_agent_steps_run_id ON agent_steps(run_id);
CREATE UNIQUE INDEX ix_agent_steps_run_id_step_index ON agent_steps(run_id, step_index);
CREATE UNIQUE INDEX ix_agent_steps_idempotency_key ON agent_steps(idempotency_key);
```

---

## API 设计

### 现有 API（修改）

#### POST /v1/agent/sessions/{session_id}/runs

**修改点：** 请求开始时创建 `agent_runs` 记录

```python
# Service 层
async def stream_agent(session_id, user_id, request):
    # 1. 创建 run（立即）
    run = await repo.create_run(
        session_id=session_id,
        input=request.input,
        type="chat",
    )
    run_id = run.id

    # 2. 实时 yield + 增量持久化 step
    async for step in agent.stream_run(state):
        # step_start → create step (status=running)
        # step_end → update step (status=success, output=...)
        yield step

    # 3. 完成时更新 run
    await repo.finish_run(run_id, output=state.output)
```

### 新增 API

#### GET /v1/agent/runs/{run_id}

获取 run 详情 + steps + messages

**Response:**
```json
{
  "id": "xxx",
  "session_id": "xxx",
  "status": "success",
  "input": "台北天气",
  "output": "台北25°C",
  "type": "chat",
  "created_at": "2026-04-07T10:00:00Z",
  "updated_at": "2026-04-07T10:00:05Z",
  "steps": [...],
  "messages": [...]
}
```

#### GET /v1/agent/runs/{run_id}/steps

获取 run 的执行步骤

**Response:**
```json
{
  "run_id": "xxx",
  "steps": [
    {
      "id": "step-1",
      "step_index": 0,
      "type": "llm",
      "name": "openai",
      "status": "success",
      "input": {},
      "output": {"content": "..."},
      "latency_ms": 1234,
      "created_at": "..."
    },
    {
      "id": "step-2",
      "step_index": 1,
      "type": "tool",
      "name": "weather",
      "status": "success",
      "input": {"city": "台北"},
      "output": {"temperature": 25},
      "latency_ms": 200,
      "created_at": "..."
    }
  ]
}
```

#### POST /v1/agent/runs/{run_id}/resume

从中断点恢复执行

**Precondition:** `run.status = running AND run.resumable = true`

**Logic:**
```python
async def resume_run(run_id, user_id, request):
    # 1. 加载 run 和已完成的 steps
    run = await repo.get_run(run_id, user_id)
    steps = await repo.get_steps(run_id)

    # 2. 找到恢复点（最后一个 non-success step）
    resume_index = find_resume_point(steps)
    # 跳过已成功的 step

    # 3. 重建 state
    state = rebuild_state(run, steps)

    # 4. 继续执行
    async for event in agent.run(state, start_from=resume_index):
        yield event
```

#### POST /v1/agent/runs/{run_id}/stop

主动停止运行中的 run

**Effect:** `run.status = interrupted`, `run.resumable = true`

**Note:** 设置为 `interrupted` 而非 `error`，表示主动中断，可 resume。

---

## SSE 事件结构

### 事件类型

| 事件 | 字段 | 说明 |
|------|------|------|
| `step_start` | run_id, step_id, step_index, type, name | Step 开始 |
| `step_end` | run_id, step_id, step_index, status, output | Step 结束（success/error） |
| `content` | run_id, step_id, content | 流式内容 |
| `tool_call` | run_id, step_id, tool, arguments | 工具调用 |
| `tool_result` | run_id, step_id, result | 工具结果 |
| `error` | run_id, step_id, step_index, error_message | 实时错误（不同于 step_end） |
| `run_end` | run_id, summary, status | 运行结束 |

### 最小事件结构

```json
{
  "run_id": "abc123",
  "step_id": "step-1",
  "step_index": 0,
  "event": "step_start",
  "data": {...}
}
```

---

## Step 状态机

### 状态流转

```
pending → running → success
                  → error
```

### 幂等协议

```python
# Tool 执行前检查
async def execute_tool(tool_name, arguments, idempotency_key):
    # 1. 检查是否已执行
    existing = await repo.get_step_by_idempotency_key(idempotency_key)
    if existing and existing.status == "success":
        return existing.output  # 跳过，直接返回

    # 2. 执行
    result = await tool.run(arguments)

    # 3. 记录
    await repo.create_step(..., idempotency_key=idempotency_key)
    return result
```

### Idempotency Key 生成

```python
def generate_idempotency_key(run_id: str, step_index: int, tool_name: str) -> str:
    import hashlib
    raw = f"{run_id}:{step_index}:{tool_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

**Uniqueness:** 同一 `run_id` 内 `run_id:step_index:tool_name` 唯一。
跨 run 可能重复（不同 run 可以用相同工具）。

---

## Replay 机制

### Replay 流程

```python
async def replay(run_id: str) -> AgentState:
    # 1. 加载 run + steps + messages
    run = await repo.get_run(run_id)
    steps = await repo.get_steps(run_id)
    messages = await repo.get_messages(run_id)

    # 2. 重建 state
    state = AgentState(
        session_id=run.session_id,
        user_input=run.input,
        messages=[{"role": m.role, "content": m.content} for m in messages],
        summary=run.session.summary,
    )

    # 3. 重放 steps（用于 UI 展示）
    for step in steps:
        state.add_step(step)

    return state
```

### Resume 流程

```python
async def resume(run_id: str) -> tuple[AgentState, int]:
    """
    返回: (重建的 state, 恢复点的 step_index)

    状态规则:
    - success: 跳过（不重复执行）
    - error: 重试（使用相同 idempotency_key）
    - pending/running: 继续执行
    """
    run = await repo.get_run(run_id)
    steps = await repo.get_steps(run_id)

    # 找到第一个未完成的 step
    for i, step in enumerate(steps):
        if step.status != "success":
            return build_state(run, steps[:i]), i

    # 全部完成，从头开始
    return build_state(run, steps), 0
```

**INTERRUPTED 状态触发:**
- `POST /runs/{id}/stop` — 客户端主动取消，设置 `status=interrupted`
- 服务端超时检测（可选，Phase 2.5）

---

## Tool 接口预留

### 隔离点: to_llm_tool()

```python
def to_llm_tool(tool: Tool) -> dict:
    """
    将 Tool 转换为 LLM function calling 格式。
    未来可扩展支持 OpenAI / MCP / Anthropic 格式。
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.schema,
        },
    }
```

### Phase 2.5 预备

- JSON Schema 标准化
- Provider-specific mapping
- Tool 版本管理

---

## 实现顺序

### Phase 2.1（本次）

1. [ ] Migration: 添加 agent_runs 表
2. [ ] Migration: agent_messages 加 run_id
3. [ ] Migration: agent_steps 加 run_id + idempotency_key
4. [ ] Model: AgentRun
5. [ ] Repository: run 相关方法
6. [ ] Service: stream_agent 增量持久化
7. [ ] SSE: step_id + step_index
8. [ ] GET /runs/{id}
9. [ ] GET /runs/{id}/steps
10. [ ] POST /runs/{id}/resume (简单版)

### Phase 2.5

- ToolSpec 标准化
- JSON Schema 验证

### Phase 3

- MCP Adapter
- Full ReAct Planner
- Embedding-based Recall

---

## 上线前检查清单

### 数据层
- [ ] agent_runs 存在
- [ ] steps 有 run_id + step_index
- [ ] messages 有 run_id
- [ ] idempotency_key 唯一约束 (per run_id+step_index)
- [ ] last_step_index 在 streaming 中更新

### 执行层
- [ ] run 在请求开始创建
- [ ] step_start → create step (status=running)
- [ ] step_end → update step (status=success + output)
- [ ] run status 正确流转
- [ ] error 状态步骤会重试（非跳过）

### 恢复能力
- [ ] replay 可还原 state
- [ ] resume 从 error/pending step 继续
- [ ] success step 不重复执行（幂等）
- [ ] POST /runs/{id}/stop → interrupted

### SSE
- [ ] 事件包含 run_id + step_id + step_index
- [ ] 前端可精确映射 event → step
- [ ] error 事件独立于 step_end
