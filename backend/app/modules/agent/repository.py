"""Agent data access layer."""
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import AgentMessage, AgentSession, AgentStep


class AgentRepository:
    """Data access for Agent sessions, messages, and steps."""

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
            .values(summary=summary, updated_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def list_sessions(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[AgentSession], int]:
        """List sessions for user (paginated)."""
        count_stmt = select(func.count()).select_from(AgentSession).where(
            AgentSession.user_id == user_id
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
    # Message
    # =========================================================================

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> AgentMessage:
        """Create a new message in a session."""
        message = AgentMessage(
            session_id=session_id,
            role=role,
            content=content,
            msg_metadata=metadata or {},
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_messages(
        self, session_id: str, limit: int = 50
    ) -> list[AgentMessage]:
        """Get recent messages for a session."""
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
        name: str | None = None,
        input: dict | None = None,
        output: dict | None = None,
        status: str = "pending",
    ) -> AgentStep:
        """Create a new step record."""
        step = AgentStep(
            session_id=session_id,
            step_index=step_index,
            type=type,
            name=name,
            input=input or {},
            output=output,
            status=status,
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
        """Update step with results."""
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

    async def get_steps(self, session_id: str) -> list[AgentStep]:
        """Get all steps for a session, ordered by step_index."""
        stmt = (
            select(AgentStep)
            .where(AgentStep.session_id == session_id)
            .order_by(AgentStep.step_index.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())