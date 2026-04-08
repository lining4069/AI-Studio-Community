# Agent System Phase 3 - MCP Adapter + ReactAgent

**Date**: 2026-04-08
**Status**: Implemented
**Phase**: Phase 3

---

## Context

Phase 3 builds on Phase 2.5's ToolSpec standardization to enable:
1. **MCP Adapter**: Integrate MCP tools via langchain-mcp-adapters
2. **ReactAgent**: Multi-step ReAct loop with Think → Action → Observe

---

## Phase 3 Goals

| Feature | Description |
|---------|-------------|
| MCP Adapter | 使用 langchain-mcp-adapters 将 MCP tools 转换为 Tool 接口 |
| ReactAgent | 多步 Think → Action → Observe 推理循环 |

---

## Architecture

### MCP Adapter Layer

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Server (e.g., Linear, Slack, GitHub)                  │
│  ├── SSE / Streamable HTTP transport                       │
│  └── MCP Protocol                                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  langchain-mcp-adapters                                    │
│  └── load_mcp_tools(connection) → list[BaseTool]         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  LangChainToolAdapter (wraps LangChain BaseTool → Tool)   │
│  └── Tool ABC interface + to_spec()                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Tool (Runtime Execution)                                   │
│  └── SimpleAgent / ReactAgent                               │
└─────────────────────────────────────────────────────────────┘
```

### ReactAgent Flow

```
┌─────────────────────────────────────────────────────────────┐
│  ReactAgent (max_loop iterations)                          │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │llm_thought│    │llm_decision│   │llm_response│
    └──────────┘    └──────────┘    └──────────┘
           │               │
           │      ┌────────┴────────┐
           │      ▼                 ▼
           │   ┌──────┐       ┌──────────┐
           │   │ tool │       │ (no tool)│
           │   └──────┘       └──────────┘
           │      │                 │
           │      ▼                 │
           │ ┌──────────┐           │
           │ │llm_observation          │
           │ └──────────┘           │
           │      │                 │
           └──────┴─────────────────┘
```

---

## Step Types (Phase 3-Ready Protocol)

### Clean Cut Design

All step types follow strict input/output structure:

| Step Type | Semantic | input | output |
|-----------|----------|-------|--------|
| `llm_thought` | LLM thinks about the problem | `{messages, tools}` | `{thought}` |
| `llm_decision` | LLM decides action | `{messages, tools, thought}` | `{decision: {type, tool, arguments}}` |
| `tool` | Tool execution | `{arguments}` | `{result}` or `{error}` |
| `llm_observation` | LLM observes result | `{tool_result}` | `{observation}` |
| `llm_response` | LLM final response | `{messages}` | `{content}` |

### SSE Event Sequence

```
Iteration N:
1. llm_thought:  STEP_START → THOUGHT → STEP_END
2. llm_decision: STEP_START → TOOL_CALL → STEP_END
3. tool:         STEP_START → TOOL_RESULT → STEP_END
4. llm_observation: STEP_START → OBSERVATION → STEP_END
(loop back to 1 or go to 5)
5. llm_response: STEP_START → CONTENT → STEP_END
```

### Key Invariants

1. **TOOL_CALL belongs to LLM step** - `step_id` is never None
2. **STEP_START ↔ STEP_END** - Every STEP_START has exactly one STEP_END
3. **Persist Before Yield** - All DB operations before SSE yield

---

## Data Models

### AgentMCPServer

```python
class AgentMCPServer(Base, TimestampMixin):
    __tablename__ = "agent_mcp_servers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transport: Mapped[str] = mapped_column(String(20), default="streamable_http")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

---

## API Changes

### AgentRunRequest

```python
class AgentRunRequest(BaseModel):
    input: str
    stream: bool = True
    debug: bool = False
    mcp_server_ids: list[str] = Field(default_factory=list)  # NEW
```

### Usage

```bash
# Create a run with MCP tools
curl -X POST '/v1/agent/sessions/{session_id}/runs' \
  -H 'Content-Type: application/json' \
  -d '{
    "input": "List my open GitHub issues",
    "mcp_server_ids": ["github-mcp-server-id"]
  }'
```

---

## File Structure

```
app/services/agent/
├── core.py                    # StepType, AgentEventType (extended)
├── simple_agent.py            # SimpleAgent (1-loop, Phase 1-2)
├── react_agent.py             # ReactAgent (ReAct loop, NEW)
├── factories.py              # create_mcp_tools() (NEW)
└── tools/
    ├── base.py               # Tool ABC
    ├── spec.py               # ToolSpec
    ├── adapters.py           # to_openai_tools(), to_mcp_tools() (NEW)
    └── langchain_adapter.py  # LangChainToolAdapter (NEW)
```

---

## Migration

```bash
# Apply migration
PGPASSWORD=Aistudio12345679 psql -h 127.0.0.1 -U ai_studio_app -d ai_studio -c "
CREATE TABLE IF NOT EXISTS agent_mcp_servers (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) NOT NULL,
    headers JSON,
    transport VARCHAR(20) NOT NULL DEFAULT 'streamable_http',
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);"
```

Or via Alembic:
```bash
alembic upgrade head
```

---

## Verification

### MCP Adapter
1. Configure an MCP server in `agent_mcp_servers` table
2. Create a run with `mcp_server_ids: [server_id]`
3. Verify MCP tools are loaded and appear in SSE events

### ReactAgent
1. Create a run with `ReactAgent(max_loop=3)`
2. Verify SSE events follow the correct sequence
3. Verify `llm_thought` → `llm_decision` → `tool` → `llm_observation` loop

---

## NOT in Phase 3

- ❌ MCP Server CRUD UI
- ❌ Multi-Agent Collaboration
- ❌ Complex Task Decomposition Planner
- ❌ Embedding-based Recall Memory (→ Future)

---

## Commit History

| Commit | Description |
|--------|-------------|
| `223e194` | feat(agent): Phase 3 - MCP Adapter and ReactAgent |
