"""Agent data access layer."""

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import AgentMessage, AgentRun, AgentSession, AgentStep
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

    async def get_steps(self, session_id: str, run_id: str | None = None) -> list[AgentStep]:
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
