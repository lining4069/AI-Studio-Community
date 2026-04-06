import pytest
from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.registry import ToolRegistry


class DummyTool(Tool):
    name: str = "dummy"
    description: str = "A dummy tool"
    schema: dict = {
        "type": "object",
        "properties": {"input": {"type": "string"}}
    }

    async def run(self, input: dict) -> dict:
        return {"result": f"processed: {input.get('input')}"}


def test_registry_register_and_get():
    """Registry stores and retrieves tools by name."""
    registry = ToolRegistry()
    tool = DummyTool()
    registry.register(tool)
    assert registry.get("dummy") is tool
    assert registry.get("nonexistent") is None


def test_registry_list_tools():
    """Registry returns tool list for LLM function calling."""
    registry = ToolRegistry()
    tool = DummyTool()
    registry.register(tool)

    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "dummy"
    assert tools[0]["description"] == "A dummy tool"
    assert "parameters" in tools[0]