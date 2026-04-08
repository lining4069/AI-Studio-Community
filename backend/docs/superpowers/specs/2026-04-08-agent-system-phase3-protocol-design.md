# Agent System Phase 3 - Clean Cut Protocol

**Date**: 2026-04-08
**Status**: Implemented
**Phase**: Phase 3 (Foundation)

---

## 目标

Phase 3 Ready Protocol：彻底重构 Step 类型和 SSE 事件结构，消除歧义，建立强 invariant。

## 设计原则

1. **Clean Cut**：不做向后兼容，新 runs 使用新协议
2. **强 Invariant**：每个 STEP_START 严格对应一个 STEP_END
3. **无悬挂状态**：TOOL_CALL 立即产生 STEP_END

---

## Step 类型

### 三种类型

| Step Type | 语义 | input | output |
|-----------|------|-------|--------|
| `llm_decision` | LLM 决定调用工具 | `{messages, tools}` | `{decision: {type, tool, arguments}}` |
| `tool` | 工具执行 | `{arguments}` | `{result}` 或 `{error}` |
| `llm_response` | LLM 最终回复 | `{messages}` | `{content}` |

### Role 字段

| Step Type | role |
|-----------|------|
| `llm_decision` | `"assistant"` |
| `tool` | `"tool"` |
| `llm_response` | `"assistant"` |

---

## SSE 事件协议

### 事件顺序（Tool Call 场景）

```
1. llm_decision: STEP_START → TOOL_CALL → STEP_END
2. tool: STEP_START → TOOL_RESULT → STEP_END
3. llm_response: STEP_START → CONTENT → STEP_END
```

### 事件详情

#### STEP_START
```json
{
  "event": "step_start",
  "data": {
    "id": "step_xxx",
    "type": "llm_decision|tool|llm_response",
    "role": "assistant|tool",
    "name": "provider_name|tool_name",
    "input": {...},
    "status": "running",
    "step_index": 0
  }
}
```

#### TOOL_CALL（仅 llm_decision step）
```json
{
  "event": "tool_call",
  "data": {
    "tool": "calculator",
    "arguments": {"expression": "2+2"},
    "step_id": "step_xxx",
    "step_index": 0
  }
}
```

#### STEP_END
```json
{
  "event": "step_end",
  "data": {
    "step_index": 0,
    "status": "success|error",
    "output": {...},
    "latency_ms": 123,
    "error": null
  }
}
```

#### TOOL_RESULT（仅 tool step）
```json
{
  "event": "tool_result",
  "data": {
    "tool": "calculator",
    "result": {"result": 4},
    "step_id": "step_xxx",
    "step_index": 1
  }
}
```

#### CONTENT（仅 llm_response step）
```json
{
  "event": "content",
  "data": {
    "content": "The result is 4."
  }
}
```

#### RUN_END
```json
{
  "event": "run_end",
  "data": {
    "output": "The result is 4.",
    "summary": "对话摘要"
  }
}
```

---

## 关键 Invariant

### 1. TOOL_CALL 归属于 LLM Step
- `TOOL_CALL.data.step_id` 不可为 None
- `TOOL_CALL.data.step_index` 标识执行顺序

### 2. STEP_START ↔ STEP_END 强对应
- 每个 STEP_START 有且只有一个 STEP_END
- 不允许"悬挂"的 running 状态

### 3. llm_decision 输出结构
```python
llm_step.output = {
    "decision": {
        "type": "tool_call",  # or "response"
        "tool": "calculator",  # if type == "tool_call"
        "arguments": {"expression": "2+2"},  # if type == "tool_call"
    }
}
```

### 4. tool 输出结构
```python
tool_step.output = {"result": {...}}  # success
tool_step.output = {"error": "..."}    # error
```

---

## 变更记录

| Date | Change |
|------|--------|
| 2026-04-08 | Initial implementation with clean cut protocol |
