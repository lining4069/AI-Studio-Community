"""
SSE (Server-Sent Events) parsing utilities for testing.

Provides functions to parse SSE streams and validate event sequences.
"""

import json
from dataclasses import dataclass


@dataclass
class SSEEvent:
    """Represents a parsed SSE event."""
    event_type: str
    data: dict
    raw_line: str = ""


async def parse_sse_events(response) -> list[SSEEvent]:
    """
    Parse SSE stream from HTTP response.

    Args:
        response: httpx AsyncClient response object

    Returns:
        List of SSEEvent objects in order
    """
    events = []
    current_event_type = None

    async for line in response.aiter_lines():
        line = line.rstrip("\n")

        if not line:
            continue

        if line.startswith("event:"):
            current_event_type = line.replace("event:", "").strip()

        elif line.startswith("data:"):
            data_str = line.replace("data:", "").strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}

            if current_event_type:
                events.append(SSEEvent(
                    event_type=current_event_type,
                    data=data,
                    raw_line=line,
                ))

    return events


async def parse_sse_raw(response) -> list[tuple[str, dict]]:
    """
    Parse SSE stream into list of (event_type, data) tuples.

    Args:
        response: httpx AsyncClient response object

    Returns:
        List of (event_type, data) tuples
    """
    events = []
    current_event_type = None

    async for line in response.aiter_lines():
        line = line.rstrip("\n")

        if not line:
            continue

        if line.startswith("event:"):
            current_event_type = line.replace("event:", "").strip()

        elif line.startswith("data:"):
            data_str = line.replace("data:", "").strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}

            if current_event_type:
                events.append((current_event_type, data))

    return events


def assert_event_sequence(events: list[SSEEvent], expected_sequence: list[str]) -> None:
    """
    Assert that events match expected sequence of event types.

    Args:
        events: List of parsed SSEEvent objects
        expected_sequence: List of expected event type strings in order

    Raises:
        AssertionError: If sequence doesn't match
    """
    actual_sequence = [e.event_type for e in events]

    assert actual_sequence == expected_sequence, (
        f"Event sequence mismatch.\n"
        f"Expected: {expected_sequence}\n"
        f"Actual:   {actual_sequence}"
    )


def assert_event_types_present(events: list[SSEEvent], required_types: list[str]) -> None:
    """
    Assert that all required event types are present in the stream.

    Args:
        events: List of parsed SSEEvent objects
        required_types: List of required event type strings

    Raises:
        AssertionError: If any required type is missing
    """
    actual_types = {e.event_type for e in events}
    missing = set(required_types) - actual_types

    assert not missing, f"Missing event types: {missing}"


def find_event(events: list[SSEEvent], event_type: str) -> SSEEvent | None:
    """Find first event of given type, or None if not found."""
    return next((e for e in events if e.event_type == event_type), None)


def find_all_events(events: list[SSEEvent], event_type: str) -> list[SSEEvent]:
    """Find all events of given type."""
    return [e for e in events if e.event_type == event_type]
