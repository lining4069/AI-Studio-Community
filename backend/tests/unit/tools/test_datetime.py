"""
Tests for DateTimeTool.

Validates current datetime retrieval.
"""

from datetime import datetime

import pytest

from app.modules.agent.tools.datetime import DateTimeTool


class TestDateTimeTool:
    """Test DateTimeTool functionality."""

    @pytest.mark.asyncio
    async def test_returns_datetime(self):
        """Test tool returns a datetime."""
        tool = DateTimeTool()
        result = await tool.run({})

        assert "datetime" in result
        assert "timezone" in result
        assert "formatted" in result

    @pytest.mark.asyncio
    async def test_datetime_format(self):
        """Test datetime is in ISO format."""
        tool = DateTimeTool()
        result = await tool.run({})

        # Should be parseable as ISO format
        dt = datetime.fromisoformat(result["datetime"].replace("Z", "+00:00"))
        assert dt.year >= 2024

    @pytest.mark.asyncio
    async def test_returns_formatted_string(self):
        """Test formatted datetime is a string."""
        tool = DateTimeTool()
        result = await tool.run({})

        assert isinstance(result["formatted"], str)
        assert "UTC" in result["formatted"]

    @pytest.mark.asyncio
    async def test_timezone_info(self):
        """Test response includes timezone info."""
        tool = DateTimeTool()
        result = await tool.run({})

        assert result["timezone"] == "UTC"


class TestDateTimeToolSchema:
    """Test DateTimeTool schema."""

    def test_tool_name(self):
        """Tool has correct name."""
        tool = DateTimeTool()
        assert tool.name == "get_current_datetime"

    def test_input_schema_empty(self):
        """Input schema accepts empty dict."""
        tool = DateTimeTool()
        schema = tool.input_schema

        # Empty object schema means no required fields
        assert schema["type"] == "object"
