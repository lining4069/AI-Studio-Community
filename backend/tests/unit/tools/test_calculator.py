"""
Tests for CalculatorTool.

Validates mathematical expression evaluation using ast.literal_eval.
"""

import pytest

from app.modules.agent.tools.calculator import CalculatorTool


class TestCalculatorTool:
    """Test CalculatorTool functionality."""

    @pytest.mark.asyncio
    async def test_basic_addition(self):
        """Test basic addition."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "2 + 3"})

        assert "result" in result
        assert result["result"] == 5.0

    @pytest.mark.asyncio
    async def test_order_of_operations(self):
        """Test that multiplication happens before addition."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "1 + 2 * 3"})

        assert result["result"] == 7.0  # 1 + (2*3) = 7, not (1+2)*3 = 9

    @pytest.mark.asyncio
    async def test_decimal_result(self):
        """Test division produces decimal."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "10 / 4"})

        assert result["result"] == 2.5

    @pytest.mark.asyncio
    async def test_power_operation(self):
        """Test power/exponent operation."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "2 ** 3"})

        assert result["result"] == 8.0

    @pytest.mark.asyncio
    async def test_parentheses(self):
        """Test parentheses override order of operations."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "(1 + 2) * 3"})

        assert result["result"] == 9.0

    @pytest.mark.asyncio
    async def test_floor_division(self):
        """Test floor division."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "17 // 5"})

        assert result["result"] == 3.0

    @pytest.mark.asyncio
    async def test_modulo(self):
        """Test modulo operation."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "17 % 5"})

        assert result["result"] == 2.0

    @pytest.mark.asyncio
    async def test_unary_negative(self):
        """Test unary negative."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "-5 + 3"})

        assert result["result"] == -2.0

    @pytest.mark.asyncio
    async def test_invalid_expression(self):
        """Test invalid expression returns error."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "invalid + syntax"})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_division_by_zero(self):
        """Test division by zero returns error."""
        tool = CalculatorTool()
        result = await tool.run({"expression": "1 / 0"})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_expression(self):
        """Test empty expression returns error."""
        tool = CalculatorTool()
        result = await tool.run({"expression": ""})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_missing_expression(self):
        """Test missing expression key returns error."""
        tool = CalculatorTool()
        result = await tool.run({})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_complex_expression(self):
        """Test complex nested expression."""
        tool = CalculatorTool()
        result = await tool.run({
            "expression": "((2 + 3) * 4 - 10) / 2 + 1"
        })

        # (5 * 4 - 10) / 2 + 1 = (20 - 10) / 2 + 1 = 10/2 + 1 = 5 + 1 = 6
        assert result["result"] == 6.0


class TestCalculatorToolSchema:
    """Test CalculatorTool schema."""

    def test_tool_name(self):
        """Tool has correct name."""
        tool = CalculatorTool()
        assert tool.name == "calculator"

    def test_input_schema_has_expression(self):
        """Input schema requires expression field."""
        tool = CalculatorTool()
        schema = tool.input_schema

        assert "expression" in schema["properties"]
        assert schema["properties"]["expression"]["type"] == "string"
