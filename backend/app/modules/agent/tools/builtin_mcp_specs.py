"""
Builtin MCP Specs.

定义内置工具的规格和处理器。
支持：calculator / datetime / rag_retrieval
"""

from datetime import datetime
import ast
import operator

from app.modules.agent.tools.builtin_mcp_registry import registry


async def calculator_handler(input: dict, rag_service) -> dict:
    """数学计算处理器。"""
    expression = input.get("expression", "")

    # 安全运算映射（只允许基本数学运算）
    safe_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op in safe_ops:
                return safe_ops[op](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp):
            op = type(node.op)
            if op in safe_ops:
                return safe_ops[op](eval_node(node.operand))
        raise ValueError(f"Unsupported: {type(node).__name__}")

    try:
        parsed = ast.parse(expression, mode='eval')
        return {"result": eval_node(parsed.body)}
    except Exception as e:
        return {"error": f"Calculation error: {e}"}


async def datetime_handler(input: dict, rag_service) -> dict:
    """日期时间处理器。"""
    now = datetime.now()
    return {
        "result": {
            "date": now.isoformat(),
            "timestamp": now.timestamp(),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
        }
    }


async def rag_retrieval_handler(input: dict, rag_service) -> dict:
    """RAG 检索处理器。"""
    if not rag_service:
        return {"error": "RAG service not available"}

    query = input.get("query", "")
    if not query:
        return {"error": "query is required"}

    try:
        results = await rag_service.retrieve(query, top_k=5)
        return {"result": results}
    except Exception as e:
        return {"error": f"RAG retrieval error: {e}"}


# 注册内置工具
registry.register("calculator", {
    "name": "calculator",
    "description": "Mathematical calculator for arithmetic expressions",
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression (e.g., '2 + 3 * 4')",
            }
        },
        "required": ["expression"]
    },
    "handler": calculator_handler,
})

registry.register("datetime", {
    "name": "datetime",
    "description": "Get current date and time",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "handler": datetime_handler,
})

registry.register("rag_retrieval", {
    "name": "rag_retrieval",
    "description": "Knowledge base retrieval for finding relevant documents",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for knowledge base",
            }
        },
        "required": ["query"]
    },
    "handler": rag_retrieval_handler,
})
