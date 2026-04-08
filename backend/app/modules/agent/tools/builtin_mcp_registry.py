"""
Builtin MCP Registry.

内置 MCP 工具注册表，提供 calculator / datetime / rag_retrieval 等内置工具。
"""

from typing import Any
from app.modules.agent.tools.base import Tool


class BuiltinMCPRegistry:
    """内置 MCP 注册表（模块级单例）。"""

    def __init__(self):
        self._specs: dict[str, dict] = {}

    def register(self, name: str, spec: dict) -> None:
        """注册一个内置工具。"""
        self._specs[name] = spec

    def get(self, name: str) -> dict | None:
        """获取内置工具规格。"""
        return self._specs.get(name)

    def create_tool(self, name: str, rag_service=None) -> "BuiltinMCPTool | None":
        """创建内置工具实例。"""
        spec = self.get(name)
        if not spec:
            return None
        return BuiltinMCPTool(spec=spec, rag_service=rag_service)


class BuiltinMCPTool(Tool):
    """内置 MCP 运行时工具。"""
    name: str
    description: str
    input_schema: dict

    def __init__(self, spec: dict, rag_service=None):
        self._spec = spec
        self.rag_service = rag_service
        self.name = spec["name"]
        self.description = spec["description"]
        self.input_schema = spec["input_schema"]

    async def run(self, input: dict) -> dict:
        handler = self._spec["handler"]
        return await handler(input, self.rag_service)


# 模块级单例
registry = BuiltinMCPRegistry()
