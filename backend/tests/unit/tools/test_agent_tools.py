"""
Test Tool ABC and ToolSpec.

Validates the tool interface contracts.
"""

from abc import ABC

from app.modules.agent.tools.base import Tool
from app.modules.agent.tools.calculator import CalculatorTool
from app.modules.agent.tools.datetime import DateTimeTool
from app.modules.agent.tools.spec import ToolSpec


class TestToolABC:
    """Test Tool abstract base class."""

    def test_tool_is_abc(self):
        """Test Tool inherits from ABC."""
        assert issubclass(Tool, ABC)

    def test_calculator_is_tool(self):
        """Test CalculatorTool is a Tool."""
        assert issubclass(CalculatorTool, Tool)

    def test_datetime_is_tool(self):
        """Test DateTimeTool is a Tool."""
        assert issubclass(DateTimeTool, Tool)

    def test_tool_has_required_attributes(self):
        """Test Tool has required class attributes."""
        tool = CalculatorTool()

        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "input_schema")

    def test_tool_has_run_method(self):
        """Test Tool has abstract run method."""
        tool = CalculatorTool()

        assert hasattr(tool, "run")
        assert callable(tool.run)

    def test_tool_has_to_spec_method(self):
        """Test Tool has to_spec method."""
        tool = CalculatorTool()

        assert hasattr(tool, "to_spec")
        assert callable(tool.to_spec)

    def test_tool_has_schema_property(self):
        """Test Tool has schema property (legacy alias)."""
        tool = CalculatorTool()

        # schema should be an alias for input_schema
        assert tool.schema == tool.input_schema


class TestToolSpec:
    """Test ToolSpec standardized contract."""

    def test_tool_spec_creation(self):
        """Test ToolSpec can be created."""
        spec = ToolSpec(
            name="test-tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
        )

        assert spec.name == "test-tool"
        assert spec.description == "A test tool"
        assert spec.input_schema["type"] == "object"

    def test_tool_to_spec(self):
        """Test Tool converts to ToolSpec."""
        tool = CalculatorTool()
        spec = tool.to_spec()

        assert isinstance(spec, ToolSpec)
        assert spec.name == tool.name
        assert spec.description == tool.description
        assert spec.input_schema == tool.input_schema

    def test_tool_spec_with_output_schema(self):
        """Test ToolSpec can include output schema."""
        spec = ToolSpec(
            name="test-tool",
            description="A test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object", "properties": {"result": {"type": "number"}}},
        )

        assert spec.output_schema is not None
        assert "result" in spec.output_schema["properties"]


class TestCalculatorToolInterface:
    """Test CalculatorTool implements Tool correctly."""

    def test_calculator_has_correct_name(self):
        """Calculator tool has correct name."""
        tool = CalculatorTool()
        assert tool.name == "calculator"

    def test_calculator_has_description(self):
        """Calculator tool has a description."""
        tool = CalculatorTool()
        assert tool.description is not None
        assert len(tool.description) > 0

    def test_calculator_has_valid_input_schema(self):
        """Calculator tool has valid JSON schema."""
        tool = CalculatorTool()
        schema = tool.input_schema

        assert schema["type"] == "object"
        assert "expression" in schema["properties"]
        assert "expression" in schema.get("required", [])

    def test_calculator_schema_matches_spec(self):
        """Calculator tool schema matches between Tool and ToolSpec."""
        tool = CalculatorTool()
        spec = tool.to_spec()

        assert tool.input_schema == spec.input_schema


class TestDateTimeToolInterface:
    """Test DateTimeTool implements Tool correctly."""

    def test_datetime_has_correct_name(self):
        """DateTime tool has correct name."""
        tool = DateTimeTool()
        assert tool.name == "get_current_datetime"

    def test_datetime_has_description(self):
        """DateTime tool has a description."""
        tool = DateTimeTool()
        assert tool.description is not None

    def test_datetime_has_valid_input_schema(self):
        """DateTime tool has valid JSON schema."""
        tool = DateTimeTool()
        schema = tool.input_schema

        assert schema["type"] == "object"
