import pytest
from datetime import datetime
from app.modules.agent.tools.datetime import DateTimeTool


@pytest.mark.asyncio
async def test_datetime_returns_current_time():
    """DateTime tool returns current datetime."""
    tool = DateTimeTool()
    result = await tool.run({})
    assert "datetime" in result
    assert "timezone" in result
    # Should be parseable as datetime
    dt = datetime.fromisoformat(result["datetime"])
    assert dt.year > 2020