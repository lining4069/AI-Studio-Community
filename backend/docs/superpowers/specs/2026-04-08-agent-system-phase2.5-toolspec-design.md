# Agent System Phase 2.5 - ToolSpec 标准化

**Date**: 2026-04-08
**Status**: Implemented
**Phase**: Phase 2.5

---

## 目标

将 Tool 系统重构为三层架构，解耦工具定义与 LLM provider 格式。

## 架构设计

### 三层职责

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Tool (Runtime Execution)                          │
│  - name, description, input_schema, output_schema           │
│  - run() - 执行逻辑                                         │
│  - to_spec() - 转换为标准化契约                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: ToolSpec (Standardized Contract)                  │
│  - Provider-agnostic JSON Schema                           │
│  - 可序列化，可存储，可传输                                  │
│  - 独立于任何 LLM provider                                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Provider Adapter (Format Conversion)               │
│  - to_openai_tool(spec) → OpenAI function calling format    │
│  - (Future) to_anthropic_tool(spec)                         │
│  - (Future) to_mcp_tool(spec)                               │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
app/services/agent/tools/
├── __init__.py                    # 公共导出
├── spec.py                        # ToolSpec 定义
├── adapters.py                    # Provider adapters
├── base.py                       # Tool ABC
└── implementations/               # 具体工具实现
    ├── __init__.py
    ├── calculator_tool.py
    ├── datetime_tool.py
    └── rag_tool.py
```

---

## 代码规范

### ToolSpec (契约层)

```python
@dataclass
class ToolSpec:
    """
    Standardized tool contract.

    Provider-agnostic representation of a tool's interface.
    """
    name: str
    description: str
    input_schema: dict[str, Any]      # JSON Schema for input
    output_schema: dict[str, Any] | None
    metadata: dict[str, Any]

    def to_openai_format(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
```

### Tool ABC (运行时层)

```python
class Tool(ABC):
    """Abstract base class for Agent tools."""

    name: str
    description: str
    input_schema: dict          # JSON Schema for input
    output_schema: dict | None

    @abstractmethod
    async def run(self, input: dict) -> dict:
        """Execute the tool with given input."""
        ...

    def to_spec(self) -> ToolSpec:
        """Convert Tool to ToolSpec (standardized contract)."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
        )
```

### Provider Adapter (转换层)

```python
def to_openai_tools(specs: list[ToolSpec]) -> list[dict]:
    """Convert list of ToolSpecs to OpenAI function calling format."""
    return [spec.to_openai_format() for spec in specs]
```

---

## 工具实现规范

### CalculatorTool

```python
class CalculatorTool(Tool):
    name: str = "calculator"
    description: str = (
        "Evaluate a mathematical expression. "
        "Use this for calculations. Input is a single expression string."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')",
            }
        },
        "required": ["expression"],
    }

    async def run(self, input: dict) -> dict:
        expression = input.get("expression", "")
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._eval_expr(tree)
            return {"result": float(result)}
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError) as e:
            return {"error": str(e)}
```

### DateTimeTool

```python
class DateTimeTool(Tool):
    name: str = "get_current_datetime"
    description: str = (
        "Get the current date and time. "
        "Use this when you need to know the current date or time. No input required."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def run(self, input: dict) -> dict:
        now = datetime.now(UTC)
        return {
            "datetime": now.isoformat(),
            "timezone": "UTC",
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
```

### RAGRetrievalTool

```python
class RAGRetrievalTool(Tool):
    name: str = "kb_retrieval"
    description: str = (
        "Retrieve relevant documents from knowledge bases. "
        "Use this when the user asks about information that might be in the knowledge base. "
        "Returns the most relevant document chunks with scores."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query text",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def run(self, input: dict) -> dict:
        query = input.get("query", "")
        top_k = input.get("top_k", self.top_k)
        # ... retrieval logic
        return {"results": [...], "query": query, "total": len(results)}
```

---

## LLM 调用转换

### SimpleAgent 中的使用

```python
def _build_llm_tools(self) -> list[dict]:
    """Convert Tool list to OpenAI function calling format via adapter."""
    specs = [t.to_spec() for t in self.tools.values()]
    return to_openai_tools(specs)
```

### 转换示例

**Input (Tool):**
```python
CalculatorTool()  # name="calculator", input_schema={...}
```

**Output (OpenAI format):**
```json
{
  "type": "function",
  "function": {
    "name": "calculator",
    "description": "Evaluate a mathematical expression...",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Mathematical expression to evaluate..."
        }
      },
      "required": ["expression"]
    }
  }
}
```

---

## 扩展设计 (Future)

### Anthropic Adapter (Phase 3)

```python
def to_anthropic_tools(specs: list[ToolSpec]) -> list[dict]:
    """Convert to Anthropic tool use format."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }
        for spec in specs
    ]
```

### MCP Adapter (Phase 3)

```python
def to_mcp_tool(spec: ToolSpec) -> dict:
    """Convert to MCP tool format."""
    return {
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_schema,
        "output_schema": spec.output_schema,
    }
```

---

## 设计原则

1. **单一职责**: Tool 负责执行，Spec 负责描述，Adapter 负责转换
2. **接口隔离**: ToolSpec 独立于 provider，不暴露 provider 细节
3. **可扩展性**: 新增 provider 只需新增 adapter，不改 Tool 层
4. **向后兼容**: 通过 `schema` 属性别名保持兼容

---

## 变更记录

| Date | Change |
|------|--------|
| 2026-04-08 | Initial implementation with 3-layer architecture |
| 2026-04-08 | Moved tools/ from app/modules/agent/ to app/services/agent/ |
| 2026-04-08 | Renamed `schema` to `input_schema` for clarity |
