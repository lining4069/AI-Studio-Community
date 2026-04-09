"""Shared enums for Agent module."""

from enum import StrEnum


class AgentTypeMode(StrEnum):
    """Supported agent runtime implementations."""

    SIMPLE = "simple"
    REACT = "react"
