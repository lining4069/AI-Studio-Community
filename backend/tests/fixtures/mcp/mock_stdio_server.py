"""Minimal local MCP stdio server fixture for integration and smoke tests."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mock-stdio-mcp")


@mcp.tool()
def echo(text: str) -> str:
    """Return the input text unchanged."""
    return text


@mcp.tool()
def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
