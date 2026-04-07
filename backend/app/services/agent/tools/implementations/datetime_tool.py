"""DateTime tool for getting current date and time."""

from datetime import UTC, datetime

from app.services.agent.tools.base import Tool


class DateTimeTool(Tool):
    """
    Tool for getting current date and time.

    Returns ISO format datetime with timezone info.
    """

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
        """
        Get current datetime.

        Args:
            input: empty dict

        Returns:
            dict with "datetime" (ISO format) and "timezone"
        """
        now = datetime.now(UTC)
        return {
            "datetime": now.isoformat(),
            "timezone": "UTC",
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
