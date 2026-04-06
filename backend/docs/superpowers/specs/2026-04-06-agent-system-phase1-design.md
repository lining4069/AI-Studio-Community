# Agent System Phase 1 Design - AI Studio Backend

> Date: 2026-04-06
> Author: AI Studio Backend Team
> Status: Approved

---

## 1. Overview

### 1.1 Goal

Build a minimum viable Agent system that supports:
- **Assistant Mode**: Lightweight Agent with RAG knowledge bases, simple prompt engineering, and conversation memory
- **Extensible Core**: Unified Agent architecture ready for Phase 2 ReAct / Tool Calling / MCP extension

### 1.2 Principles

- **Evolutionary Design**: Phase 1 = "weak Agent", not "another system"
- **No Premature Abstraction**: Implement only what's needed, leave extension points
- **Iterative Development**: Phase 1 → Phase 2 → Phase 3 roadmap

### 1.3 Phase Roadmap

| Phase | Focus | Key Features |
|-------|-------|--------------|
| Phase 1 | Assistant + Agent Core | Session/Memory/Step, Tool Registry, Local Tools, SSE Streaming |
| Phase 2 | Tool Ecosystem | MCP Adapter, Dynamic Tool Loading, Extended Tools |
| Phase 3 | Full ReAct | Multi-step Planning, Planner Interface, Advanced Memory |

---

## 2. Architecture

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                               │
│   Session API / Run API (SSE Event Streaming)              │
├─────────────────────────────────────────────────────────────┤
│                     Agent Core                              │
│   SimpleAgent.run() → LLM → Tool? → Execute → LLM        │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────┐│
│  │  Planner  │  │  Step     │  │   Tool    │  │ Memory  ││
│  │ (LLM Dec.)│  │  Schema   │  │ Registry  │  │(Summary)││
│  └───────────┘  └───────────┘  └───────────┘  └─────────┘│
├─────────────────────────────────────────────────────────────┤
│                    Tool Layer                               │
│   RAG Tool / Calculator / DateTime (Local)                │
│   langchain-mcp-adapters (Phase 2 Reserved)               │
├─────────────────────────────────────────────────────────────┤
│               Existing System (Reuse)                      │
│   LLM Provider / RAG / Knowledge Base                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Agent Core Concept

**Five Core Objects:**
1. **Agent** - Entry point, orchestrates execution
2. **AgentContext** - Input unified入口 (user_input, session_id, kb_ids)
3. **AgentState** - Runtime state (messages, steps, scratchpad)
4. **Step** - Minimal execution unit (llm/tool/retrieval)
5. **Tool** - Optional capability (name, description, schema, run)

---

## 3. Database Design

### 3.1 Tables

#### agent_sessions

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Session ID |
| user_id | UUID | Owner |
| agent_id | UUID (nullable) | Agent config (future) |
| title | TEXT | Session title |
| mode | TEXT | "assistant" (future: "agent") |
| summary | TEXT (nullable) | Conversation summary (light memory) |
| created_at | TIMESTAMP | Create time |
| updated_at | TIMESTAMP | Last update time |

#### agent_messages

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Message ID |
| session_id | UUID (FK) | Parent session |
| role | TEXT | "user" / "assistant" / "system" |
| content | TEXT | Message content |
| metadata | JSONB | Extra data (nullable) |
| created_at | TIMESTAMP | Create time |

#### agent_steps

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Step ID |
| session_id | UUID (FK) | Parent session |
| step_index | INT | Execution order |
| type | TEXT | "llm" / "tool" / "retrieval" |
| name | TEXT (nullable) | Tool/model name |
| input | JSONB | Step input |
| output | JSONB (nullable) | Step output |
| thought | TEXT (nullable) | ReAct thought (future) |
| status | TEXT | "pending" / "running" / "success" / "error" |
| error | TEXT (nullable) | Error message |
| latency_ms | INT (nullable) | Execution latency |
| created_at | TIMESTAMP | Create time |

### 3.2 Design Principles

- **State is Reconstructible**: Don't store giant JSON state blobs
- **Separation of Concerns**: messages = human-readable, steps = execution trace
- **step_index Required**: For replay and debug ordering

---

## 4. Tool System

### 4.1 Tool Interface (Self-developed)

```python
class Tool(ABC):
    name: str
    description: str
    schema: dict  # JSON Schema

    @abstractmethod
    async def run(self, input: dict) -> dict:
        """Execute tool with input dict, return result dict"""
        pass
```

### 4.2 ToolRegistry

```python
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """Return tool list for LLM function calling"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.schema
            }
            for t in self._tools.values()
        ]
```

### 4.3 Phase 1 Local Tools

| Tool | Name | Description | Schema |
|------|------|-------------|--------|
| RAG Retrieval | `kb_retrieval` | Query knowledge bases | `{kb_ids: [], query: str, top_k: int}` |
| Calculator | `calculator` | Mathematical calculations | `{expression: str}` |
| DateTime | `get_current_datetime` | Current date and time | `{}` |

### 4.4 Phase 2 Extension

```
ToolRegistry + MCP Adapter
    ├── Local Tools (Phase 1)
    └── MCP Tools (Phase 2, via langchain-mcp-adapters)
```

---

## 5. Agent Core Execution

### 5.1 SimpleAgent Flow

```
User Input
    │
    ▼
Agent.run(session_id, user_input)
    │
    ├── Load Memory: summary + recent messages
    ├── Build Prompt: [summary] + [messages] + [tools]
    │
    ▼
LLM(messages, tools)
    │
    ├── if tool_call → execute tool → LLM(..., tool_result)
    └── else → direct response
    │
    ├── Record Steps to agent_steps
    ├── Generate Summary (when conversation ends)
    └── Yield SSE Events
```

### 5.2 Loop Strategy

**Phase 1**: Maximum 1 loop iteration
- LLM decides whether to call tool
- If tool called: execute → feed result back to LLM → final response
- If no tool: direct LLM response

**Phase 2+**: Extend to multi-step ReAct (same interface)

### 5.3 Prompt Construction

```
System Prompt:
[You are an AI Assistant with knowledge base access]

Memory (if exists):
[Summary of previous conversation]

Recent Messages:
[Last N messages]

Available Tools:
[Tool registry list]

User: {user_input}
```

---

## 6. API Design

### 6.1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/agent/sessions` | Create session |
| GET | `/v1/agent/sessions/{session_id}` | Get session |
| GET | `/v1/agent/sessions/{session_id}/messages` | Get messages |
| GET | `/v1/agent/sessions/{session_id}/steps` | Get execution steps |
| POST | `/v1/agent/sessions/{session_id}/runs` | Run agent (SSE) |

### 6.2 Create Session

**Request:**
```json
{
  "user_id": "xxx",
  "title": "RAG Assistant",
  "kb_ids": ["kb1", "kb2"]
}
```

**Response:**
```json
{
  "id": "session_id",
  "title": "RAG Assistant",
  "mode": "assistant",
  "created_at": "..."
}
```

### 6.3 Run Agent (SSE Streaming)

**Request:**
```json
{
  "input": "Tell me about our product",
  "stream": true,
  "debug": false
}
```

### 6.4 SSE Event Format

```json
event: session_start
data: {"session_id": "xxx"}

event: step_start
data: {"type": "llm", "name": "gpt-4o"}

event: token
data: {"token": "Our"}

event: tool_call
data: {"tool": "kb_retrieval", "arguments": {"query": "product", "kb_ids": [...]}}

event: tool_result
data: {"tool": "kb_retrieval", "result": ["doc1", "doc2"]}

event: step_end
data: {"type": "llm", "output": "Based on the knowledge base..."}

event: run_end
data: {"summary": "User asked about product, retrieved from KB..."}
```

---

## 7. Module Structure

### 7.1 New Module: `app/modules/agent/`

```
app/modules/agent/
├── __init__.py
├── models.py          # ORM: AgentSession, AgentMessage, AgentStep
├── schema.py          # Pydantic: Request/Response
├── repository.py      # Data access
├── service.py         # Business logic + Agent Core
├── router.py         # API routes
└── tools/
    ├── __init__.py
    ├── base.py        # Tool ABC
    ├── registry.py    # ToolRegistry
    └── implementations/
        ├── __init__.py
        ├── rag_tool.py
        ├── calculator_tool.py
        └── datetime_tool.py
```

### 7.2 Service Layer Extension

```
app/services/
├── providers/         # (existing)
└── agent/
    ├── __init__.py
    ├── core.py       # SimpleAgent, AgentState, Step
    ├── planner.py    # (Phase 1: LLM direct decision)
    └── factories.py  # Tool factory
```

---

## 8. Integration with Existing System

### 8.1 Reuse Components

| Component | Integration |
|-----------|-------------|
| LLM Provider | Via `app/services/providers/model_factory.py` |
| Knowledge Base | Via `app/modules/knowledge_base/service.py` |
| RAG Retrieval | Via `app/services/rag/retrieval_service.py` |
| DB Session | Via existing `DBAsyncSession` dependency |
| Auth | Via existing `CurrentUser` dependency |

### 8.2 Model Factory Extension

```python
# app/services/agent/factories.py
async def create_agent_tools(kb_ids: list[str]) -> list[Tool]:
    tools = [CalculatorTool(), DateTimeTool()]
    if kb_ids:
        tools.append(await create_rag_tool(kb_ids))
    return tools
```

---

## 9. Implementation Order

### Phase 1 Task List

1. **Database Migration**
   - Create `agent_sessions`, `agent_messages`, `agent_steps` tables

2. **Tool System**
   - Implement `Tool` ABC
   - Implement `ToolRegistry`
   - Implement local tools: RAG, Calculator, DateTime

3. **Agent Core**
   - Implement `AgentState`
   - Implement `Step` dataclass
   - Implement `SimpleAgent.run()`

4. **Service Layer**
   - `AgentRepository`
   - `AgentService` (create session, run agent)
   - Tool factory integration

5. **API Layer**
   - Session CRUD endpoints
   - Run endpoint with SSE streaming
   - Events: step_start/end, token, tool_call/result, run_end

6. **Memory Integration**
   - Summary generation on conversation end
   - Prompt builder with summary + messages

---

## 10. Future Phase Extensions

### Phase 2: Tool Ecosystem
- MCP Server configuration table
- MCP Adapter via `langchain-mcp-adapters`
- Dynamic tool loading

### Phase 3: Full ReAct
- `Planner` interface
- `ReActPlanner` implementation
- Multi-step loop with thought/observation

---

## Appendix: Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Assistant vs Agent | Unified Core | Avoid duplicated logic |
| Memory | Light Summary | Phase 1 only, extensible later |
| Tool System | Self-developed + LangChain Phase 2 | Control now, ecosystem later |
| Planner | LLM Direct Decision | Phase 1 simplicity, rule-based fallback |
| Streaming | Full Event SSE | Frontend visualization, debug |
| DB Schema | 3 Core Tables | Minimal, reconstructible state |

---

*Document Version: 1.0*
*Last Updated: 2026-04-06*
