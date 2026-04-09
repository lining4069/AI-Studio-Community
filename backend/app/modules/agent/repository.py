"""Agent data access layer."""

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.agent.enums import AgentTypeMode
from app.modules.agent.models import (
    AgentConfig,
    AgentConfigKB,
    AgentConfigMCP,
    AgentConfigTool,
    AgentMCPServer,
    AgentMessage,
    AgentRun,
    AgentSession,
    AgentStep,
)
from app.utils.datetime_utils import now_utc


class AgentRepository:
    """Data access for Agent sessions, messages, steps, and runs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Session
    # =========================================================================

    async def create_session(
        self,
        user_id: int,
        title: str | None = None,
        mode: str = "assistant",
    ) -> AgentSession:
        """Create a new agent session."""
        session = AgentSession(
            user_id=user_id,
            title=title,
            mode=mode,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_session(self, session_id: str, user_id: int) -> AgentSession | None:
        """Get session by ID (must belong to user)."""
        stmt = select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def update_summary(self, session_id: str, summary: str) -> None:
        """Update session summary (light memory)."""
        stmt = (
            update(AgentSession)
            .where(AgentSession.id == session_id)
            .values(summary=summary, updated_at=now_utc())
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def list_sessions(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[AgentSession], int]:
        """List sessions for user (paginated)."""
        count_stmt = (
            select(func.count())
            .select_from(AgentSession)
            .where(AgentSession.user_id == user_id)
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(AgentSession)
            .where(AgentSession.user_id == user_id)
            .order_by(AgentSession.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    # =========================================================================
    # Run (Phase 2)
    # =========================================================================

    async def create_run(
        self,
        session_id: str,
        input: str,
        type: str = "chat",
        trace_id: str | None = None,
    ) -> AgentRun:
        """Create a new run (immediately when API request starts)."""
        run = AgentRun(
            session_id=session_id,
            input=input,
            type=type,
            trace_id=trace_id,
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_run(self, run_id: str, user_id: int | None = None) -> AgentRun | None:
        """Get run by ID (optionally verify user ownership via session)."""
        if user_id is not None:
            stmt = (
                select(AgentRun)
                .join(AgentSession, AgentRun.session_id == AgentSession.id)
                .where(AgentRun.id == run_id, AgentSession.user_id == user_id)
            )
        else:
            stmt = select(AgentRun).where(AgentRun.id == run_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def update_run(
        self,
        run_id: str,
        status: str | None = None,
        output: str | None = None,
        error: str | None = None,
        last_step_index: int | None = None,
    ) -> None:
        """Update run fields."""
        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status
        if output is not None:
            updates["output"] = output
        if error is not None:
            updates["error"] = error
        if last_step_index is not None:
            updates["last_step_index"] = last_step_index

        if updates:
            stmt = update(AgentRun).where(AgentRun.id == run_id).values(**updates)
            await self.db.execute(stmt)
            await self.db.flush()

    async def finish_run(
        self,
        run_id: str,
        status: str,
        output: str | None = None,
        error: str | None = None,
    ) -> None:
        """Mark run as finished (success/error/interrupted)."""
        await self.update_run(
            run_id=run_id,
            status=status,
            output=output,
            error=error,
        )

    # =========================================================================
    # Message
    # =========================================================================

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        run_id: str | None = None,
        metadata: dict | None = None,
    ) -> AgentMessage:
        """Create a new message in a session (optionally owned by a run)."""
        message = AgentMessage(
            session_id=session_id,
            run_id=run_id,
            role=role,
            content=content,
            msg_metadata=metadata or {},
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_messages(
        self, session_id: str, run_id: str | None = None, limit: int = 50
    ) -> list[AgentMessage]:
        """Get messages for a session or run, ordered by created_at."""
        if run_id:
            stmt = (
                select(AgentMessage)
                .where(AgentMessage.run_id == run_id)
                .order_by(AgentMessage.created_at.asc())
                .limit(limit)
            )
        else:
            stmt = (
                select(AgentMessage)
                .where(AgentMessage.session_id == session_id)
                .order_by(AgentMessage.created_at.asc())
                .limit(limit)
            )
        return list((await self.db.execute(stmt)).scalars().all())

    # =========================================================================
    # Step
    # =========================================================================

    async def create_step(
        self,
        session_id: str,
        step_index: int,
        type: str,
        run_id: str | None = None,
        name: str | None = None,
        step_input: dict | None = None,
        output: dict | None = None,
        status: str = "pending",
        error: str | None = None,
        latency_ms: int | None = None,
        idempotency_key: str | None = None,
    ) -> AgentStep:
        """Create a new step record (INSERT on step_start)."""
        step = AgentStep(
            session_id=session_id,
            run_id=run_id,
            step_index=step_index,
            type=type,
            name=name,
            input=step_input or {},
            output=output,
            status=status,
            error=error,
            latency_ms=latency_ms,
            idempotency_key=idempotency_key,
        )
        self.db.add(step)
        await self.db.flush()
        await self.db.refresh(step)
        return step

    async def update_step(
        self,
        step_id: str,
        output: dict | None = None,
        status: str | None = None,
        error: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Update step with results (UPDATE on step_end)."""
        updates: dict[str, Any] = {}
        if output is not None:
            updates["output"] = output
        if status is not None:
            updates["status"] = status
        if error is not None:
            updates["error"] = error
        if latency_ms is not None:
            updates["latency_ms"] = latency_ms

        if updates:
            stmt = update(AgentStep).where(AgentStep.id == step_id).values(**updates)
            await self.db.execute(stmt)
            await self.db.flush()

    async def get_steps(
        self, session_id: str, run_id: str | None = None
    ) -> list[AgentStep]:
        """Get steps for a session or run, ordered by step_index."""
        if run_id:
            stmt = (
                select(AgentStep)
                .where(AgentStep.run_id == run_id)
                .order_by(AgentStep.step_index.asc())
            )
        else:
            stmt = (
                select(AgentStep)
                .where(AgentStep.session_id == session_id)
                .order_by(AgentStep.step_index.asc())
            )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_step_by_idempotency_key(
        self, idempotency_key: str
    ) -> AgentStep | None:
        """Get step by idempotency_key for deduplication."""
        stmt = select(AgentStep).where(AgentStep.idempotency_key == idempotency_key)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # =========================================================================
    # MCP Server (Phase 3)
    # =========================================================================

    async def get_mcp_servers(
        self,
        server_ids: list[str] | None = None,
        enabled_only: bool = True,
        user_id: int | None = None,
    ) -> list[AgentMCPServer]:
        """
        Get MCP servers by IDs or all enabled servers.

        Args:
            server_ids: Optional list of server IDs to fetch
            enabled_only: If True, only return enabled servers
            user_id: If provided, filter by user ownership

        Returns:
            List of AgentMCPServer instances
        """
        stmt = select(AgentMCPServer)

        if server_ids:
            stmt = stmt.where(AgentMCPServer.id.in_(server_ids))

        if enabled_only:
            stmt = stmt.where(AgentMCPServer.enabled.is_(True))

        if user_id is not None:
            stmt = stmt.where(AgentMCPServer.user_id == user_id)

        return list((await self.db.execute(stmt)).scalars().all())

    # =========================================================================
    # AgentConfig CRUD (Phase 4)
    # =========================================================================

    async def create_config(
        self,
        user_id: int,
        name: str,
        description: str | None = None,
        llm_model_id: str | None = None,
        agent_type: AgentTypeMode = AgentTypeMode.SIMPLE,
        max_loop: int = 5,
        system_prompt: str | None = None,
        enabled: bool = True,
    ) -> AgentConfig:
        """Create a new agent config."""
        config = AgentConfig(
            user_id=user_id,
            name=name,
            description=description,
            llm_model_id=llm_model_id,
            agent_type=agent_type.value,
            max_loop=max_loop,
            system_prompt=system_prompt,
            enabled=enabled,
        )
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def get_config(
        self, config_id: str, user_id: int | None = None
    ) -> AgentConfig | None:
        """Get agent config by ID (optionally verify ownership)."""
        stmt = select(AgentConfig).where(AgentConfig.id == config_id)
        if user_id is not None:
            stmt = stmt.where(AgentConfig.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_config_detail(
        self, config_id: str, user_id: int | None = None
    ) -> AgentConfig | None:
        """Get agent config with all related resources eagerly loaded."""
        stmt = (
            select(AgentConfig)
            .options(
                selectinload(AgentConfig.tools),
                selectinload(AgentConfig.mcp_links),
                selectinload(AgentConfig.kb_links),
            )
            .where(AgentConfig.id == config_id)
        )
        if user_id is not None:
            stmt = stmt.where(AgentConfig.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_configs(
        self,
        user_id: int,
        enabled_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentConfig], int]:
        """List agent configs for user (paginated)."""
        count_stmt = (
            select(func.count())
            .select_from(AgentConfig)
            .where(AgentConfig.user_id == user_id)
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(AgentConfig)
            .where(AgentConfig.user_id == user_id)
            .order_by(AgentConfig.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        if enabled_only:
            stmt = stmt.where(AgentConfig.enabled.is_(True))

        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def update_config(
        self,
        config_id: str,
        user_id: int,
        name: str | None = None,
        description: str | None = None,
        llm_model_id: str | None = None,
        agent_type: AgentTypeMode | None = None,
        max_loop: int | None = None,
        system_prompt: str | None = None,
        enabled: bool | None = None,
    ) -> AgentConfig | None:
        """Update agent config fields."""
        config = await self.get_config(config_id, user_id)
        if not config:
            return None

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if llm_model_id is not None:
            updates["llm_model_id"] = llm_model_id
        if agent_type is not None:
            updates["agent_type"] = agent_type.value
        if max_loop is not None:
            updates["max_loop"] = max_loop
        if system_prompt is not None:
            updates["system_prompt"] = system_prompt
        if enabled is not None:
            updates["enabled"] = enabled

        if updates:
            stmt = (
                update(AgentConfig).where(AgentConfig.id == config_id).values(**updates)
            )
            await self.db.execute(stmt)
            await self.db.flush()
            await self.db.refresh(config)

        return config

    async def delete_config(self, config_id: str, user_id: int) -> bool:
        """Delete agent config (cascade deletes linked tools/MCP/KB)."""
        config = await self.get_config(config_id, user_id)
        if not config:
            return False
        await self.db.delete(config)
        await self.db.flush()
        return True

    # =========================================================================
    # Config Tools (Phase 4)
    # =========================================================================

    async def add_config_tool(
        self,
        config_id: str,
        tool_name: str,
        tool_config: dict | None = None,
        enabled: bool = True,
    ) -> AgentConfigTool:
        """Add a tool to a config."""
        tool = AgentConfigTool(
            config_id=config_id,
            tool_name=tool_name,
            tool_config=tool_config or {},
            enabled=enabled,
        )
        self.db.add(tool)
        await self.db.flush()
        await self.db.refresh(tool)
        return tool

    async def update_config_tool(
        self,
        tool_id: int,
        config_id: str | None = None,
        user_id: int | None = None,
        tool_config: dict | None = None,
        enabled: bool | None = None,
    ) -> AgentConfigTool | None:
        """Update a config tool."""
        stmt = select(AgentConfigTool).where(AgentConfigTool.id == tool_id)
        if config_id is not None:
            stmt = stmt.where(AgentConfigTool.config_id == config_id)
        if user_id is not None:
            stmt = stmt.join(AgentConfig).where(AgentConfig.user_id == user_id)
        tool = (await self.db.execute(stmt)).scalar_one_or_none()
        if not tool:
            return None

        if tool_config is not None:
            tool.tool_config = tool_config
        if enabled is not None:
            tool.enabled = enabled

        await self.db.flush()
        await self.db.refresh(tool)
        return tool

    async def delete_config_tool(
        self,
        tool_id: int,
        config_id: str | None = None,
        user_id: int | None = None,
    ) -> bool:
        """Delete a config tool."""
        stmt = select(AgentConfigTool).where(AgentConfigTool.id == tool_id)
        if config_id is not None:
            stmt = stmt.where(AgentConfigTool.config_id == config_id)
        if user_id is not None:
            stmt = stmt.join(AgentConfig).where(AgentConfig.user_id == user_id)
        tool = (await self.db.execute(stmt)).scalar_one_or_none()
        if not tool:
            return False
        await self.db.delete(tool)
        await self.db.flush()
        return True

    async def get_config_tools(self, config_id: str) -> list[AgentConfigTool]:
        """Get all tools for a config."""
        stmt = (
            select(AgentConfigTool)
            .where(AgentConfigTool.config_id == config_id)
            .order_by(AgentConfigTool.id)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    # =========================================================================
    # Config MCP Servers (Phase 4)
    # =========================================================================

    async def add_config_mcp_server(
        self,
        config_id: str,
        mcp_server_id: str,
    ) -> AgentConfigMCP:
        """Link an MCP server to a config."""
        link = AgentConfigMCP(
            config_id=config_id,
            mcp_server_id=mcp_server_id,
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def delete_config_mcp_server(
        self,
        link_id: int,
        config_id: str | None = None,
        user_id: int | None = None,
    ) -> bool:
        """Unlink an MCP server from a config."""
        stmt = select(AgentConfigMCP).where(AgentConfigMCP.id == link_id)
        if config_id is not None:
            stmt = stmt.where(AgentConfigMCP.config_id == config_id)
        if user_id is not None:
            stmt = stmt.join(AgentConfig).where(AgentConfig.user_id == user_id)
        link = (await self.db.execute(stmt)).scalar_one_or_none()
        if not link:
            return False
        await self.db.delete(link)
        await self.db.flush()
        return True

    async def get_config_mcp_links(self, config_id: str) -> list[AgentConfigMCP]:
        """Get all MCP server links for a config."""
        stmt = (
            select(AgentConfigMCP)
            .where(AgentConfigMCP.config_id == config_id)
            .order_by(AgentConfigMCP.id)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    # =========================================================================
    # Config KB Links (Phase 4)
    # =========================================================================

    async def add_config_kb(
        self,
        config_id: str,
        kb_id: str,
        kb_config: dict | None = None,
    ) -> AgentConfigKB:
        """Link a knowledge base to a config."""
        link = AgentConfigKB(
            config_id=config_id,
            kb_id=kb_id,
            kb_config=kb_config or {},
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def delete_config_kb(
        self,
        link_id: int,
        config_id: str | None = None,
        user_id: int | None = None,
    ) -> bool:
        """Unlink a knowledge base from a config."""
        stmt = select(AgentConfigKB).where(AgentConfigKB.id == link_id)
        if config_id is not None:
            stmt = stmt.where(AgentConfigKB.config_id == config_id)
        if user_id is not None:
            stmt = stmt.join(AgentConfig).where(AgentConfig.user_id == user_id)
        link = (await self.db.execute(stmt)).scalar_one_or_none()
        if not link:
            return False
        await self.db.delete(link)
        await self.db.flush()
        return True

    async def get_config_kb_links(self, config_id: str) -> list[AgentConfigKB]:
        """Get all KB links for a config."""
        stmt = (
            select(AgentConfigKB)
            .where(AgentConfigKB.config_id == config_id)
            .order_by(AgentConfigKB.id)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    # =========================================================================
    # MCP Server CRUD (Phase 4)
    # =========================================================================

    async def create_mcp_server(
        self,
        user_id: int,
        name: str,
        transport: str = "streamable_http",
        url: str | None = None,
        headers: dict | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        enabled: bool = True,
    ) -> AgentMCPServer:
        """Create a new MCP server for a user."""
        server = AgentMCPServer(
            user_id=user_id,
            name=name,
            transport=transport,
            url=url,
            headers=headers,
            command=command,
            args=args,
            env=env,
            cwd=cwd,
            enabled=enabled,
        )
        self.db.add(server)
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def get_mcp_server(
        self, server_id: str, user_id: int | None = None
    ) -> AgentMCPServer | None:
        """Get MCP server by ID (optionally verify ownership)."""
        stmt = select(AgentMCPServer).where(AgentMCPServer.id == server_id)
        if user_id is not None:
            stmt = stmt.where(AgentMCPServer.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def update_mcp_server(
        self,
        server_id: str,
        user_id: int,
        name: str | None = None,
        transport: str | None = None,
        url: str | None = None,
        headers: dict | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        enabled: bool | None = None,
    ) -> AgentMCPServer | None:
        """Update MCP server fields."""
        server = await self.get_mcp_server(server_id, user_id)
        if not server:
            return None

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if transport is not None:
            updates["transport"] = transport
        if url is not None:
            updates["url"] = url
        if headers is not None:
            updates["headers"] = headers
        if command is not None:
            updates["command"] = command
        if args is not None:
            updates["args"] = args
        if env is not None:
            updates["env"] = env
        if cwd is not None:
            updates["cwd"] = cwd
        if enabled is not None:
            updates["enabled"] = enabled

        if updates:
            stmt = (
                update(AgentMCPServer)
                .where(AgentMCPServer.id == server_id)
                .values(**updates)
            )
            await self.db.execute(stmt)
            await self.db.flush()
            await self.db.refresh(server)

        return server

    async def delete_mcp_server(self, server_id: str, user_id: int) -> bool:
        """Delete MCP server."""
        server = await self.get_mcp_server(server_id, user_id)
        if not server:
            return False
        await self.db.delete(server)
        await self.db.flush()
        return True

    # =========================================================================
    # Session Config Binding (Phase 4)
    # =========================================================================

    async def update_session_config(
        self, session_id: str, config_id: str | None
    ) -> None:
        """Update session's config_id binding."""
        stmt = (
            update(AgentSession)
            .where(AgentSession.id == session_id)
            .values(config_id=config_id, updated_at=now_utc())
        )
        await self.db.execute(stmt)
        await self.db.flush()

    # =========================================================================
    # Run Snapshot (Phase 4)
    # =========================================================================

    async def update_run_snapshot(self, run_id: str, snapshot: dict) -> None:
        """Update run's config_snapshot."""
        stmt = (
            update(AgentRun)
            .where(AgentRun.id == run_id)
            .values(config_snapshot=snapshot)
        )
        await self.db.execute(stmt)
        await self.db.flush()
