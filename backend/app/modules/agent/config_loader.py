"""
AgentConfigLoader - loads AgentConfig from DB to DomainConfig.

Converts ORM models to domain objects for business logic layer.
"""

from app.modules.agent.domain import (
    DomainConfig,
    KBConfigItem,
    MCPConfigItem,
    ToolConfigItem,
)
from app.modules.agent.models import AgentConfig, AgentConfigMCP


class AgentConfigLoader:
    """
    Loads AgentConfig from database with all relations.

    Usage:
        loader = AgentConfigLoader(session)
        domain_config = await loader.load(config_id, user_id)
    """

    def __init__(self, db_session):
        """
        Initialize with database session.

        Args:
            db_session: SQLAlchemy async session
        """
        self.db = db_session

    async def load(self, config_id: str, user_id: int) -> DomainConfig | None:
        """
        Load AgentConfig by ID and verify ownership.

        Args:
            config_id: AgentConfig ID
            user_id: User ID for ownership verification

        Returns:
            DomainConfig if found and owned by user, None otherwise

        Raises:
            PermissionError: If config doesn't belong to user
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(AgentConfig)
            .options(
                selectinload(AgentConfig.tools),
                selectinload(AgentConfig.mcp_links).selectinload(AgentConfigMCP.mcp_server),
                selectinload(AgentConfig.kb_links),
            )
            .where(AgentConfig.id == config_id)
        )

        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            return None

        # Verify ownership
        if config.user_id != user_id:
            raise PermissionError(
                f"Config {config_id} does not belong to user {user_id}"
            )

        return self._to_domain(config)

    async def load_by_user(
        self, user_id: int, enabled_only: bool = True
    ) -> list[DomainConfig]:
        """
        Load all AgentConfigs for a user.

        Args:
            user_id: User ID
            enabled_only: Only return enabled configs

        Returns:
            List of DomainConfig objects
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(AgentConfig)
            .options(
                selectinload(AgentConfig.tools),
                selectinload(AgentConfig.mcp_links).selectinload(AgentConfigMCP.mcp_server),
                selectinload(AgentConfig.kb_links),
            )
            .where(AgentConfig.user_id == user_id)
        )

        if enabled_only:
            stmt = stmt.where(AgentConfig.enabled)

        result = await self.db.execute(stmt)
        configs = result.scalars().all()

        return [self._to_domain(c) for c in configs]

    def _to_domain(self, config: AgentConfig) -> DomainConfig:
        """Convert ORM model to DomainConfig."""
        return DomainConfig(
            id=config.id,
            user_id=config.user_id,
            name=config.name,
            agent_type=config.agent_type or "simple",
            max_loop=config.max_loop or 5,
            system_prompt=config.system_prompt,
            llm_model_id=config.llm_model_id,
            tools=[
                ToolConfigItem(
                    tool_name=t.tool_name,
                    tool_config=t.tool_config or {},
                    enabled=t.enabled,
                )
                for t in config.tools
            ],
            mcp_servers=[
                MCPConfigItem(
                    mcp_server_id=link.mcp_server_id,
                    name=link.mcp_server.name if link.mcp_server else "",
                    transport=link.mcp_server.transport
                    if link.mcp_server
                    else "streamable_http",
                    url=link.mcp_server.url if link.mcp_server else None,
                    headers=link.mcp_server.headers if link.mcp_server else None,
                    command=link.mcp_server.command if link.mcp_server else None,
                    args=link.mcp_server.args if link.mcp_server else None,
                    env=link.mcp_server.env if link.mcp_server else None,
                    cwd=link.mcp_server.cwd if link.mcp_server else None,
                    enabled=link.mcp_server.enabled if link.mcp_server else True,
                )
                for link in config.mcp_links
            ],
            kbs=[
                KBConfigItem(
                    kb_id=link.kb_id,
                    kb_config=link.kb_config or {},
                )
                for link in config.kb_links
            ],
        )
