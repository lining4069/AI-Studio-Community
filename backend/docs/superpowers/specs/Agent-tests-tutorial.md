# Agent System 测试套件教程

**日期**: 2026-04-08
**Phase**: Testing Infrastructure

---

## 概述

本测试套件基于 `Agent系统测试验证流程.md` 设计，覆盖 Agent 系统的完整生命周期：
- Config CRUD + 工具关联
- Session 管理
- Run 执行 + SSE 事件流
- Resume / Stop 操作
- MCP Server 管理

---

## 测试架构

### 三层测试模型

```
┌─────────────────────────────────────────────────────────────┐
│                    e2e/test_agent_flow.py                  │
│         Config → Session → Run → Resume/Stop               │
│                     完整工作流测试                          │
├─────────────────────────────────────────────────────────────┤
│                  integration/test_api.py                    │
│              HTTP 请求/响应 + Schema 验证                   │
├─────────────────────────────────────────────────────────────┤
│  unit/core/test_core.py        │  unit/tools/*.py           │
│  Step, AgentState, AgentEvent  │  CalculatorTool, DateTime  │
│         核心数据结构             │        工具实现           │
└─────────────────────────────────────────────────────────────┘
        ▲ 快速、无 I/O          │  ▲ 有 I/O、异步
        └────────────────────────┴──┘
```

---

## 目录结构

```
tests/
├── conftest.py                      # 全局 fixtures
│   ├── MockLLMProvider              # 可控 LLM Mock
│   ├── snapshot()                   # 快照测试 fixture
│   └── db_session, repo, service    # 依赖注入
├── utils/
│   └── sse.py                      # SSE 解析工具
├── unit/                           # 单元测试（快速、无 I/O）
│   ├── core/
│   │   └── test_core.py           # Step, AgentState, AgentEvent
│   └── tools/
│       ├── test_calculator.py       # CalculatorTool
│       ├── test_datetime.py         # DateTimeTool
│       ├── test_rag_tool.py        # RAGRetrievalTool
│       └── test_agent_tools.py     # Tool ABC, ToolSpec
├── integration/                     # API 层测试
│   └── test_api.py                # HTTP 请求/响应验证
├── e2e/                           # 端到端测试
│   └── test_agent_flow.py         # Config → Session → Run → Resume/Stop
└── snapshots/                      # 快照存储目录
```

---

## 核心组件

### 1. MockLLMProvider

可控的 LLM Mock，解决 LLM 输出不可预测的问题：

```python
# 注册预期响应
mock_llm.register(
    "计算 1+2*3",
    {
        "content": "我来计算",
        "tool_calls": [{
            "id": "call_123",
            "function": {
                "name": "calculator",
                "arguments": {"expression": "1+2*3"},
            },
        }],
    },
)

# 使用
await mock_llm.achat(messages=[...])
```

**特点**:
- 支持 substring 匹配（`"计算"` 匹配所有包含 "计算" 的 prompt）
- 支持顺序注册（`register_tool_sequence`）
- 记录 call_history 用于调试

### 2. Snapshot Testing

解决 Agent 输出难以断言的问题：

```python
def test_run_snapshot(snapshot):
    result = run_agent()
    snapshot.assert_match(result)  # 首次创建，后续验证一致性
```

**工作流程**:
1. 首次运行：写入 `tests/snapshots/{test_name}.json`
2. 后续运行：与快照对比，不一致则失败并生成 `.actual.json`

### 3. SSE 解析工具

```python
from tests.utils.sse import parse_sse_events, assert_event_sequence

events = await parse_sse_events(response)

# 验证事件顺序
assert_event_sequence(events, ["step_start", "tool_call", "tool_result", "run_end"])

# 查找特定事件
run_end = find_event(events, "run_end")
assert run_end.data["status"] == "success"
```

---

## 运行方式

### 安装依赖

```bash
pip install pytest pytest-asyncio httpx aiosqlite
```

### 运行测试

```bash
# 运行所有测试
pytest -v

# 仅运行单元测试（快速）
pytest -m unit -v

# 仅运行 E2E 测试
pytest -m e2e -v

# 仅运行集成测试
pytest -m integration -v

# 生成/更新快照
pytest --snapshot-update

# 运行特定文件
pytest tests/unit/tools/test_calculator.py -v

# 运行特定测试
pytest tests/unit/tools/test_calculator.py::TestCalculatorTool::test_basic_addition -v
```

### pytest 配置 (pytest.ini)

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short

markers =
    unit: Unit tests (fast, no I/O)
    integration: Integration tests (API layer)
    e2e: End-to-end tests (full workflow)
    slow: Slow running tests
```

---

## 测试用例示例

### Unit Test - CalculatorTool

```python
@pytest.mark.asyncio
async def test_calculator_order_of_operations():
    """测试乘法优先于加法"""
    tool = CalculatorTool()
    result = await tool.run({"expression": "1 + 2 * 3"})

    assert result["result"] == 7.0  # 1 + (2*3) = 7, not (1+2)*3 = 9
```

### Unit Test - Tool ABC

```python
def test_calculator_is_tool():
    """验证 CalculatorTool 实现了 Tool 接口"""
    assert issubclass(CalculatorTool, Tool)

def test_tool_to_spec():
    """验证 Tool 可转换为 ToolSpec"""
    tool = CalculatorTool()
    spec = tool.to_spec()

    assert isinstance(spec, ToolSpec)
    assert spec.name == tool.name
```

### E2E Test - Config + Tool

```python
@pytest.mark.asyncio
async def test_add_duplicate_tool_raises_conflict(
    self, repo: AgentRepository, sample_user_id: int
):
    """重复添加工具应抛出 ConflictException"""
    config = await repo.create_config(
        user_id=sample_user_id,
        name="duplicate-tool-test",
    )

    await repo.add_config_tool(
        config_id=config.id,
        tool_name="calculator",
    )

    with pytest.raises(ConflictException):
        await repo.add_config_tool(
            config_id=config.id,
            tool_name="calculator",
        )
```

### E2E Test - Run Execution

```python
@pytest.mark.asyncio
async def test_stream_run_direct_response(
    self,
    service: AgentService,
    repo: AgentRepository,
    sample_user_id: int,
    mock_llm: MockLLMProvider,
):
    """测试无工具调用时的直接响应"""
    mock_llm.register(
        "hello",
        {"content": "Hello! How can I help you?"},
    )

    session = await repo.create_session(user_id=sample_user_id)

    with patch.object(service, "_get_llm_for_session", return_value=mock_llm):
        result_state = await service.run_agent(
            session_id=session.id,
            user_id=sample_user_id,
            user_input="hello",
            stream=False,
        )

        assert result_state.finished is True
```

---

## 验证清单

基于 `Agent系统测试验证流程.md` 的完整验证：

| # | 验证项 | 测试位置 |
|---|--------|----------|
| 1 | 创建 Config，添加 calculator + datetime tool | `e2e/test_agent_flow.py` |
| 2 | 重复添加同名 tool → 409 Conflict | `e2e/test_agent_flow.py::TestValidationRules` |
| 3 | 关联 MCP Server，创建 Run | `e2e/test_agent_flow.py::TestMCPServerOperations` |
| 4 | config_snapshot 正确保存 | `e2e/test_agent_flow.py::TestRunExecution` |
| 5 | 修改 Config，重新 Run | `e2e/test_agent_flow.py::TestRunExecution` |
| 6 | agent_type="react" → ReactAgent | `e2e/test_agent_flow.py::TestRunExecution` |
| 7 | 用户隔离（403 Forbidden）| `e2e/test_agent_flow.py::TestValidationRules` |
| 8 | Resume 中断的 Run | `e2e/test_agent_flow.py::TestResumeStop` |
| 9 | Stop 正在运行的 Run | `e2e/test_agent_flow.py::TestResumeStop` |
| 10 | SSE 事件顺序正确 | `utils/sse.py::assert_event_sequence` |

---

## 下一步升级建议

### 1. Mock LLM 完善

在 `conftest.py` 中添加预设 Mock：

```python
@pytest.fixture
def mock_llm_with_calculator():
    """预配置的计算器 Mock"""
    def setup(prompt="计算", tool_expr="1+2*3", answer="7"):
        mock = MockLLMProvider()
        mock.register(prompt, {
            "content": f"我来计算 {tool_expr}",
            "tool_calls": [{
                "function": {"name": "calculator", "arguments": {"expression": tool_expr}}
            }]
        })
        mock.register(str({"result": float(answer)}), {"content": f"{tool_expr} = {answer}"})
        return mock
    return setup
```

### 2. CI 集成

```yaml
# .github/workflows/test.yml
name: Agent Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx aiosqlite

      - name: Run tests
        run: pytest -v
```

### 3. SSE Snapshot

```python
@pytest.mark.asyncio
async def test_run_sse_snapshot(client, auth_headers, snapshot):
    """SSE 事件流快照测试"""
    response = await client.post(
        f"/v1/agent/sessions/{session_id}/runs",
        headers=auth_headers,
        json={"input": "计算 1+2*3", "stream": True},
    )

    events = await parse_sse_events(response)
    event_data = [{"type": e.event_type, "data": e.data} for e in events]

    snapshot.assert_match({"events": event_data})
```

### 4. 压测

使用 Locust 或 k6 进行负载测试。

---

## 判断标准

一个 Agent 系统进入「工程级 AI 系统」行列的标志：

| 标志 | 说明 |
|------|------|
| ✅ Mock LLM | LLM 输出可控，测试不依赖外部 API |
| ✅ Snapshot | 结果可回归，任何改动立即可见 |
| ✅ CI | PR 自动跑测试，代码改动不失焦 |
| ✅ 分层测试 | Unit → Integration → E2E，每层覆盖不同风险 |

---

## 关键文件

| 文件 | 说明 |
|------|------|
| `tests/conftest.py` | 全局 fixtures：MockLLMProvider, Snapshot, DB Session |
| `tests/utils/sse.py` | SSE 事件解析和断言工具 |
| `tests/e2e/test_agent_flow.py` | 完整工作流测试 |
| `tests/unit/tools/test_*.py` | 各工具的单元测试 |
| `tests/unit/core/test_core.py` | 核心数据结构的单元测试 |
| `pytest.ini` | pytest 配置 |
