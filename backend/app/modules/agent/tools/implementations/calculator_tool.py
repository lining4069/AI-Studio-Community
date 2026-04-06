"""Calculator tool for mathematical expression evaluation."""
import ast
import operator
from typing import Any

from app.modules.agent.tools.base import Tool


class CalculatorTool(Tool):
    """
    Tool for evaluating mathematical expressions safely.

    Uses ast.literal_eval for safe parsing of numeric expressions.
    Supports: +, -, *, /, //, %, **, parentheses.
    """

    name: str = "calculator"
    description: str = (
        "Evaluate a mathematical expression. "
        "Use this for calculations. Input is a single expression string."
    )
    schema: dict = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')",
            }
        },
        "required": ["expression"],
    }

    # Supported operators mapping
    _ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def _eval_expr(self, node: ast.AST) -> Any:
        """Recursively evaluate an AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            return self._ops[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            return self._ops[type(node.op)](self._eval_expr(node.operand))
        elif isinstance(node, ast.Expression):
            return self._eval_expr(node.body)
        else:
            raise ValueError(f"Unsupported operation: {type(node).__name__}")

    async def run(self, input: dict) -> dict:
        """
        Evaluate a mathematical expression.

        Args:
            input: dict with "expression" key

        Returns:
            dict with "result" float or "error" string
        """
        expression = input.get("expression", "")
        try:
            # Parse and evaluate safely
            tree = ast.parse(expression, mode="eval")
            result = self._eval_expr(tree)
            # Convert to float for consistency
            return {"result": float(result)}
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError) as e:
            return {"error": str(e)}