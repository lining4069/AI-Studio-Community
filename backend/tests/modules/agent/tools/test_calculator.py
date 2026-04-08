import pytest
from app.modules.agent.tools.calculator import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_basic():
    """Calculator evaluates basic math expressions."""
    tool = CalculatorTool()
    result = await tool.run({"expression": "2 + 3 * 4"})
    assert result["result"] == 14.0


@pytest.mark.asyncio
async def test_calculator_decimal():
    """Calculator handles decimal results."""
    tool = CalculatorTool()
    result = await tool.run({"expression": "10 / 3"})
    assert abs(result["result"] - 3.333333) < 0.01


@pytest.mark.asyncio
async def test_calculator_invalid():
    """Calculator returns error for invalid expressions."""
    tool = CalculatorTool()
    result = await tool.run({"expression": "invalid + syntax"})
    assert "error" in result