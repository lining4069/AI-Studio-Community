"""
Agent repository for database operations.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import Agent, AgentSession, McpServer, WebSearchConfig

# ============================================================================
# WebSearch Config Repository
# ============================================================================


class WebSearchConfigRepository:
    """Repository for WebSearchConfig database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, data) -> WebSearchConfig:
        """Create a new WebSearchConfig"""
        model = WebSearchConfig(
            user_id=user_id,
            name=data.name,
            provider=data.provider.value,
            encrypted_api_key=data.encrypted_api_key,
            search_count=data.search_count,
            is_active=data.is_active,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, config_id: str, user_id: int) -> WebSearchConfig | None:
        """Get WebSearchConfig by ID"""
        stmt = select(WebSearchConfig).where(
            WebSearchConfig.id == config_id, WebSearchConfig.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[WebSearchConfig], int]:
        """List WebSearchConfigs with pagination"""
        count_stmt = (
            select(func.count())
            .select_from(WebSearchConfig)
            .where(WebSearchConfig.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(WebSearchConfig)
            .where(WebSearchConfig.user_id == user_id)
            .order_by(WebSearchConfig.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def update(
        self,
        config: WebSearchConfig,
        data,
    ) -> WebSearchConfig:
        """Update a WebSearchConfig"""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Handle enum conversion
        if "provider" in update_data and update_data["provider"]:
            update_data["provider"] = update_data["provider"].value

        for field, value in update_data.items():
            setattr(config, field, value)

        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def delete(self, config: WebSearchConfig) -> None:
        """Delete a WebSearchConfig"""
        await self.db.delete(config)
        await self.db.flush()


# ============================================================================
# MCP Server Repository
# ============================================================================


class McpServerRepository:
    """Repository for McpServer database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, data) -> McpServer:
        """Create a new McpServer"""
        model = McpServer(
            user_id=user_id,
            name=data.name,
            url=data.url,
            connection_type=data.connection_type.value,
            encrypted_auth_token=data.encrypted_auth_token,
            enabled=data.enabled,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, server_id: str, user_id: int) -> McpServer | None:
        """Get McpServer by ID"""
        stmt = select(McpServer).where(
            McpServer.id == server_id, McpServer.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[McpServer], int]:
        """List McpServers with pagination"""
        count_stmt = (
            select(func.count())
            .select_from(McpServer)
            .where(McpServer.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(McpServer)
            .where(McpServer.user_id == user_id)
            .order_by(McpServer.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def list_by_ids(self, server_ids: list[str], user_id: int) -> list[McpServer]:
        """Get multiple McpServers by IDs"""
        if not server_ids:
            return []
        stmt = select(McpServer).where(
            McpServer.id.in_(server_ids),
            McpServer.user_id == user_id,
            McpServer.enabled,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        server: McpServer,
        data,
    ) -> McpServer:
        """Update a McpServer"""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Handle enum conversion
        if "connection_type" in update_data and update_data["connection_type"]:
            update_data["connection_type"] = update_data["connection_type"].value

        for field, value in update_data.items():
            setattr(server, field, value)

        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def delete(self, server: McpServer) -> None:
        """Delete a McpServer"""
        await self.db.delete(server)
        await self.db.flush()


# ============================================================================
# Agent Repository
# ============================================================================


class AgentRepository:
    """Repository for Agent database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, data) -> Agent:
        """Create a new Agent"""
        model = Agent(
            user_id=user_id,
            name=data.name,
            description=data.description,
            llm_model_id=data.llm_model_id,
            llm_temperature=data.llm_temperature,
            llm_max_tokens=data.llm_max_tokens,
            llm_top_p=data.llm_top_p,
            llm_timeout=data.llm_timeout,
            system_prompt=data.system_prompt,
            kb_retrieval_mode=data.kb_retrieval_mode.value,
            kb_ids=data.kb_ids,
            mcp_ids=data.mcp_ids,
            enable_websearch=data.enable_websearch,
            websearch_config_id=data.websearch_config_id,
            max_steps=data.max_steps,
            return_raw_response=data.return_raw_response,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_id(self, agent_id: str, user_id: int) -> Agent | None:
        """Get Agent by ID"""
        stmt = select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[Agent], int]:
        """List Agents with pagination"""
        count_stmt = (
            select(func.count()).select_from(Agent).where(Agent.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(Agent)
            .where(Agent.user_id == user_id)
            .order_by(Agent.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def update(
        self,
        agent: Agent,
        data,
    ) -> Agent:
        """Update an Agent"""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Handle enum conversion
        if "kb_retrieval_mode" in update_data and update_data["kb_retrieval_mode"]:
            update_data["kb_retrieval_mode"] = update_data["kb_retrieval_mode"].value

        for field, value in update_data.items():
            setattr(agent, field, value)

        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def delete(self, agent: Agent) -> None:
        """Delete an Agent"""
        await self.db.delete(agent)
        await self.db.flush()


# ============================================================================
# Agent Session Repository
# ============================================================================


class AgentSessionRepository:
    """Repository for AgentSession database operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        agent_id: str,
        session_id: str,
        initial_messages: list[dict] = None,
    ) -> AgentSession:
        """Create a new AgentSession"""
        model = AgentSession(
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            messages=initial_messages or [],
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def get_by_session_id(
        self, session_id: str, user_id: int, agent_id: str
    ) -> AgentSession | None:
        """Get AgentSession by session_id"""
        stmt = select(AgentSession).where(
            AgentSession.session_id == session_id,
            AgentSession.user_id == user_id,
            AgentSession.agent_id == agent_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        user_id: int,
        agent_id: str,
        session_id: str,
    ) -> AgentSession:
        """Get existing session or create new one"""
        session = await self.get_by_session_id(session_id, user_id, agent_id)
        if session:
            return session
        return await self.create(user_id, agent_id, session_id)

    async def update_messages(
        self, session: AgentSession, messages: list[dict]
    ) -> AgentSession:
        """Update session messages"""
        session.messages = messages
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def append_message(
        self, session: AgentSession, message: dict
    ) -> AgentSession:
        """Append a message to session"""
        messages = session.messages.copy()
        messages.append(message)
        return await self.update_messages(session, messages)

    async def delete_by_agent(self, agent_id: str) -> None:
        """Delete all sessions for an agent"""
        stmt = select(AgentSession).where(AgentSession.agent_id == agent_id)
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        for session in sessions:
            await self.db.delete(session)
        await self.db.flush()
