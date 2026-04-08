"""
Domain objects for Agent system.

Pure Python dataclasses, decoupled from ORM.
Used for business logic layer to pass configuration data.
"""

from dataclasses import dataclass, field


@dataclass
class ToolConfigItem:
    """A single built-in tool with its configuration."""

    tool_name: str
    tool_config: dict  # e.g., {"api_key": "...", "search_depth": "basic"}
    enabled: bool = True


@dataclass
class MCPConfigItem:
    """A linked MCP server configuration."""

    mcp_server_id: str
    name: str
    transport: str
    url: str | None = None
    headers: dict | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    enabled: bool = True


@dataclass
class KBConfigItem:
    """A linked knowledge base configuration."""

    kb_id: str
    kb_config: dict  # e.g., {"top_k": 5, "rank_threshold": 0.7}


@dataclass
class DomainConfig:
    """
    AgentConfig domain object, decoupled from ORM.

    Represents the fully loaded configuration including all tool configs,
    MCP servers, and knowledge bases. Used by ToolBuilder to construct
    tool instances.
    """

    id: str
    user_id: int
    name: str
    agent_type: str  # "simple" | "react"
    max_loop: int
    system_prompt: str | None
    llm_model_id: str | None
    tools: list[ToolConfigItem] = field(default_factory=list)
    mcp_servers: list[MCPConfigItem] = field(default_factory=list)
    kbs: list[KBConfigItem] = field(default_factory=list)

    def to_snapshot(self) -> dict:
        """Serialize to JSON snapshot for storage in AgentRun.config_snapshot."""
        import dataclasses

        return dataclasses.asdict(self)

    @classmethod
    def from_snapshot(cls, data: dict) -> "DomainConfig":
        """Deserialize from AgentRun.config_snapshot for historical run replay."""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            name=data["name"],
            agent_type=data["agent_type"],
            max_loop=data["max_loop"],
            system_prompt=data.get("system_prompt"),
            llm_model_id=data.get("llm_model_id"),
            tools=[ToolConfigItem(**t) for t in data.get("tools", [])],
            mcp_servers=[MCPConfigItem(**m) for m in data.get("mcp_servers", [])],
            kbs=[KBConfigItem(**k) for k in data.get("kbs", [])],
        )
