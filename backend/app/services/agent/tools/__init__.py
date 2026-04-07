"""
Agent Tools - Tool ABC, ToolSpec, and Provider Adapters.

Architecture:
- Tool (ABC): Runtime execution layer
- ToolSpec: Standardized contract (provider-agnostic)
- Adapters: Convert ToolSpec to provider-specific formats
"""

from app.services.agent.tools.base import Tool
from app.services.agent.tools.spec import ToolSpec

__all__ = ["Tool", "ToolSpec"]
