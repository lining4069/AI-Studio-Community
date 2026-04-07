"""Agent service - business logic and orchestration."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse
from loguru import logger

from app.common.exceptions import NotFoundException
from app.modules.agent.models import AgentSession
from app.modules.agent.repository import AgentRepository
from app.modules.agent.schema import (
    AgentRunRequest,
    AgentSessionCreate,
    AgentSessionResponse,
)
from app.modules.llm_model.repository import LlmModelRepository
from app.services.agent.core import AgentEventType, AgentState
from app.services.agent.factories import create_agent_tools
from app.services.agent.simple_agent import SimpleAgent
from app.services.providers.model_factory import create_llm


class AgentService:
    """
    Business logic for Agent system.

    Handles session management, agent execution, and SSE streaming.
    """

    def __init__(
        self,
        repo: AgentRepository,
        llm_model_repo: LlmModelRepository,
    ):
        self.repo = repo
        self.llm_model_repo = llm_model_repo

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self, user_id: int, data: AgentSessionCreate
    ) -> AgentSessionResponse:
        """Create a new agent session."""
        session = await self.repo.create_session(
            user_id=user_id,
            title=data.title,
            mode=data.mode,
        )
        return AgentSessionResponse.model_validate(session)

    async def get_session(self, session_id: str, user_id: int) -> AgentSession:
        """Get session or raise NotFoundException."""
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundException("Agent Session", session_id)
        return session

    async def list_sessions(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[AgentSession], int]:
        """List sessions for user."""
        return await self.repo.list_sessions(user_id, page, page_size)

    # =========================================================================
    # Message & Step Access
    # =========================================================================

    async def get_messages(
        self, session_id: str, user_id: int, limit: int = 50
    ) -> list[dict]:
        """Get messages for a session."""
        await self.get_session(session_id, user_id)
        messages = await self.repo.get_messages(session_id, limit=limit)
        return [
            {
                "id": m.id,
                "session_id": m.session_id,
                "run_id": m.run_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    async def get_steps(self, session_id: str, user_id: int) -> list[dict]:
        """Get execution steps for a session."""
        await self.get_session(session_id, user_id)
        steps = await self.repo.get_steps(session_id)
        return [
            {
                "id": s.id,
                "session_id": s.session_id,
                "run_id": s.run_id,
                "step_index": s.step_index,
                "type": s.type,
                "name": s.name,
                "input": s.input,
                "output": s.output,
                "status": s.status,
                "error": s.error,
                "latency_ms": s.latency_ms,
                "created_at": s.created_at.isoformat(),
            }
            for s in steps
        ]

    # =========================================================================
    # Run Access (Phase 2)
    # =========================================================================

    async def get_run(self, run_id: str, user_id: int) -> dict:
        """Get run by ID (verifies user ownership via session)."""
        run = await self.repo.get_run(run_id, user_id)
        if not run:
            raise NotFoundException("AgentRun", run_id)
        return {
            "id": run.id,
            "session_id": run.session_id,
            "type": run.type,
            "status": run.status,
            "input": run.input,
            "output": run.output,
            "error": run.error,
            "last_step_index": run.last_step_index,
            "resumable": run.resumable,
            "trace_id": run.trace_id,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        }

    async def get_run_steps(self, run_id: str, user_id: int) -> list[dict]:
        """Get steps for a specific run (verifies user ownership via session)."""
        # First verify run exists and belongs to user
        run = await self.repo.get_run(run_id, user_id)
        if not run:
            raise NotFoundException("AgentRun", run_id)
        # Pass session_id as required positional arg, run_id as filter
        steps = await self.repo.get_steps(session_id=run.session_id, run_id=run_id)
        return [
            {
                "id": s.id,
                "session_id": s.session_id,
                "run_id": s.run_id,
                "step_index": s.step_index,
                "type": s.type,
                "name": s.name,
                "input": s.input,
                "output": s.output,
                "status": s.status,
                "error": s.error,
                "latency_ms": s.latency_ms,
                "created_at": s.created_at.isoformat(),
            }
            for s in steps
        ]

    async def stop_run(self, run_id: str, user_id: int) -> dict:
        """
        Stop an running run (marks as interrupted).

        Note: This only works if the run is still streaming.
        If the stream has already completed, this has no effect.
        """
        run = await self.repo.get_run(run_id, user_id)
        if not run:
            raise NotFoundException("AgentRun", run_id)

        if run.status != "running":
            # Already finished, cannot stop
            return {
                "id": run.id,
                "status": run.status,
                "message": f"Run already {run.status}",
            }

        await self.repo.update_run(run_id=run_id, status="interrupted")
        return {
            "id": run.id,
            "status": "interrupted",
            "message": "Run stop requested",
        }

    # =========================================================================
    # Agent Execution
    # =========================================================================

    async def run_agent(
        self,
        session_id: str,
        user_id: int,
        request: AgentRunRequest,
    ) -> dict:
        """
        Run agent (non-streaming, for debugging/testing).

        Returns full result dict with output, summary, steps.
        """
        session = await self.get_session(session_id, user_id)

        # Load messages for context
        db_messages = await self.repo.get_messages(session_id)
        history = [{"role": m.role, "content": m.content} for m in db_messages]

        # Get KB IDs from session config (stored in metadata or separate table)
        kb_ids = getattr(session, "kb_ids", []) or []

        # Create LLM
        llm = await self._get_llm_for_session(session, user_id)

        # Create tools
        tools = await create_agent_tools(kb_ids=kb_ids, rag_service=None)

        # Build initial state
        state = AgentState(
            session_id=session_id,
            user_input=request.input,
            messages=history,
            summary=session.summary,
        )

        # Run agent
        agent = SimpleAgent(llm=llm, tools=tools)
        result_state = await agent.run(state)

        # Persist user message
        await self.repo.create_message(
            session_id=session_id,
            role="user",
            content=request.input,
        )

        # Persist assistant response
        if result_state.output:
            await self.repo.create_message(
                session_id=session_id,
                role="assistant",
                content=result_state.output,
            )

        # Persist steps
        for step in result_state.steps:
            await self.repo.create_step(
                session_id=session_id,
                step_index=step.step_index or 0,
                type=step.type,
                name=step.name,
                input=step.input,
                output=step.output,
                status=step.status,
                error=step.error,
                latency_ms=step.latency_ms,
            )

        # Update session summary if needed
        if result_state.summary:
            await self.repo.update_summary(session_id, result_state.summary)

        # Generate summary if conversation has enough messages
        # Build full message list including new exchange
        all_messages = history + [
            {"role": "user", "content": request.input},
            {"role": "assistant", "content": result_state.output or ""},
        ]
        if len(all_messages) >= 3:  # Only if meaningful conversation
            new_summary = await self._generate_summary(
                messages=all_messages,
                llm=llm,
            )
            if new_summary:
                # Merge with existing summary
                combined_summary = (
                    (session.summary + "\n" + new_summary)
                    if session.summary
                    else new_summary
                )
                await self.repo.update_summary(session_id, combined_summary)

        return result_state.to_result()

    async def stream_agent(
        self,
        session_id: str,
        user_id: int,
        request: AgentRunRequest,
    ) -> StreamingResponse:
        """
        Run agent with SSE streaming and incremental step persistence.

        Phase 2: Run is created immediately, steps are persisted on
        step_start (INSERT) and step_end (UPDATE) for crash recovery.

        Returns StreamingResponse with event stream.
        """
        session = await self.get_session(session_id, user_id)

        # Load messages for context
        db_messages = await self.repo.get_messages(session_id)
        history = [{"role": m.role, "content": m.content} for m in db_messages]

        # Get KB IDs from session config
        kb_ids = getattr(session, "kb_ids", []) or []

        # Create LLM
        llm = await self._get_llm_for_session(session, user_id)

        # Create tools (with RAG service if KBs configured)
        rag_service = None  # TODO: Create RAG service from knowledge_base
        tools = await create_agent_tools(kb_ids=kb_ids, rag_service=rag_service)

        # Build initial state
        state = AgentState(
            session_id=session_id,
            user_input=request.input,
            messages=history,
            summary=session.summary,
        )

        # Generate run_id for SSE event tracking
        run_id = uuid.uuid4().hex

        # Run streaming agent
        agent = SimpleAgent(llm=llm, tools=tools, run_id=run_id)

        async def event_generator() -> AsyncGenerator[bytes, None]:
            # Create run immediately (Phase 2: request start = run creation)
            run = await self.repo.create_run(
                session_id=session_id,
                input=request.input,
                trace_id=run_id,
            )

            # Persist user message with run_id
            await self.repo.create_message(
                session_id=session_id,
                run_id=run.id,
                role="user",
                content=request.input,
            )

            # Stream events - now yields (Step, AgentEvent) tuples
            async for step, event in agent.stream_run(state):
                # Handle run_end specially: persist data BEFORE yield
                # This ensures data is saved even if client disconnects
                if event.event == AgentEventType.RUN_END:
                    # CRITICAL: All persistence MUST happen before yield
                    # 1. Persist assistant message using state.output (not event.data)
                    if state.output:
                        await self.repo.create_message(
                            session_id=session_id,
                            run_id=run.id,
                            role="assistant",
                            content=state.output,
                        )

                    # 2. Generate summary using incremental compression
                    current_exchange = [
                        {"role": "user", "content": request.input},
                        {"role": "assistant", "content": state.output or ""},
                    ]
                    new_summary = await self._generate_summary(
                        messages=current_exchange,
                        llm=llm,
                        previous_summary=session.summary,
                    )
                    if new_summary:
                        combined_summary = (
                            (session.summary + "\n" + new_summary)
                            if session.summary
                            else new_summary
                        )
                        await self.repo.update_summary(session_id, combined_summary)

                    # 3. Mark run as finished
                    await self.repo.finish_run(
                        run_id=run.id,
                        status="success" if state.finished else "error",
                        output=state.output,
                    )

                    # 4. Update event data with summary for SSE
                    event.data["summary"] = new_summary or session.summary
                    event.data["run_id"] = run.id

                    # 5. Yield run_end SSE
                    yield event.to_sse().encode("utf-8")
                    continue

                # Inject run_id into event data
                event.data["run_id"] = run.id

                if event.event == AgentEventType.STEP_START and step is not None:
                    # step_start: INSERT step record with status=running
                    db_step = await self.repo.create_step(
                        session_id=session_id,
                        run_id=run.id,
                        step_index=step.step_index,
                        type=step.type,
                        name=step.name,
                        step_input=step.input,
                        status="running",
                        idempotency_key=f"{run.id}:{step.step_index}:{step.type}",
                    )
                    step.id = db_step.id
                    event.data.pop("id", None)
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == AgentEventType.STEP_END and step is not None:
                    # step_end: UPDATE step record
                    event_data = event.data
                    await self.repo.update_step(
                        step_id=step.id,
                        status=event_data.get("status"),
                        output=event_data.get("output"),
                        latency_ms=event_data.get("latency_ms"),
                        error=event_data.get("error"),
                    )
                    event.data["step_id"] = step.id
                    event.data["step_index"] = event_data.get("step_index")

                elif event.event == AgentEventType.TOOL_CALL and step is not None:
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == AgentEventType.TOOL_RESULT and step is not None:
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == AgentEventType.CONTENT and step is not None:
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == AgentEventType.ERROR:
                    if step is not None:
                        event.data["step_id"] = step.id
                        event.data["step_index"] = step.step_index

                # Forward event to SSE client
                yield event.to_sse().encode("utf-8")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def _get_llm_for_session(self, session: AgentSession, user_id: int):
        """
        Get LLM provider for session.

        TODO: Get from session config or user preference.
        For now, gets first available LLM model for user.
        """
        # Get first LLM model for user (placeholder)
        models, _ = await self.llm_model_repo.list_by_user(user_id, page=1, page_size=1)
        if not models:
            raise ValueError("No LLM model configured")

        return create_llm(models[0])

    async def _generate_summary(
        self,
        messages: list[dict],
        llm: Any,
        previous_summary: str | None = None,
    ) -> str | None:
        """
        Generate conversation summary using LLM.

        Uses incremental compression strategy:
        - If previous_summary exists: summarize(previous_summary + recent 2-4 messages)
        - Otherwise: summarize(recent messages)

        This avoids re-summarizing the entire conversation history each time.
        """
        if len(messages) < 2:
            return None

        try:
            summary_prompt = ""

            if previous_summary:
                # Incremental compression: previous summary + recent messages
                summary_prompt = (
                    "Summarize the conversation updates concisely in 2-3 sentences. "
                    "The previous summary captures earlier context.\n\n"
                    f"Previous Summary:\n{previous_summary}\n\n"
                    f"Recent Messages ({len(messages)}):\n"
                )
            else:
                # First summary: use recent messages
                summary_prompt = (
                    "Summarize the following conversation concisely in 2-3 sentences. "
                    "Focus on the main topics discussed and any key conclusions.\n\n"
                )

            # Use recent 4 messages for compression window
            for msg in messages[-4:]:
                summary_prompt += f"{msg['role']}: {msg['content'][:300]}\n"

            summary_response = await llm.achat(
                messages=[{"role": "user", "content": summary_prompt}],
                tools=None,
            )

            if isinstance(summary_response, dict):
                return summary_response.get("content", "").strip()
            elif isinstance(summary_response, str):
                return summary_response.strip()
            return str(summary_response)

        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return None

    # =========================================================================
    # Resume (Phase 2)
    # =========================================================================

    async def resume_agent(
        self,
        run_id: str,
        user_id: int,
        request: AgentRunRequest,
    ) -> StreamingResponse:
        """
        Resume an interrupted run from last successful step.

        Resume strategy:
        1. Get original run and verify ownership
        2. Get successful steps to rebuild state
        3. Create new run for continuation (original run stays as-is)
        4. Stream from where we left off

        SSOT principle: Don't restore state, rebuild it from facts.
        """
        # 1. Get original run
        original_run = await self.repo.get_run(run_id, user_id)
        if not original_run:
            raise NotFoundException("AgentRun", run_id)

        # 2. Get session for context
        session = await self.get_session(original_run.session_id, user_id)

        # 3. Get successful steps from original run (for state reconstruction)
        all_steps = await self.repo.get_steps(
            session_id=original_run.session_id, run_id=run_id
        )
        successful_steps = [s for s in all_steps if s.status == "success"]

        # 4. Rebuild conversation history from successful steps
        #    - Get messages from original run
        #    - Append successful step outputs to scratchpad
        db_messages = await self.repo.get_messages(original_run.session_id)
        history = [{"role": m.role, "content": m.content} for m in db_messages]

        # Rebuild tool_results from successful tool steps
        tool_results: dict[str, Any] = {}
        for step in successful_steps:
            if step.type == "tool" and step.name and step.output:
                tool_results[step.name] = step.output

        # 5. Get KB IDs from session
        kb_ids = getattr(session, "kb_ids", []) or []

        # 6. Create LLM
        llm = await self._get_llm_for_session(session, user_id)

        # 7. Create tools
        rag_service = None
        tools = await create_agent_tools(kb_ids=kb_ids, rag_service=rag_service)

        # 8. Build initial state from successful steps + summary
        #    Skip all successful steps (they're already in history/scratchpad)
        last_step_index = successful_steps[-1].step_index if successful_steps else -1

        state = AgentState(
            session_id=original_run.session_id,
            user_input=request.input,
            messages=history,
            summary=session.summary,
            tool_results=tool_results,
        )

        # 9. Generate new run_id for SSE tracking
        new_run_id = uuid.uuid4().hex

        # 10. Run streaming agent
        agent = SimpleAgent(llm=llm, tools=tools, run_id=new_run_id)

        async def event_generator() -> AsyncGenerator[bytes, None]:
            # Create new run (continuation)
            new_run = await self.repo.create_run(
                session_id=original_run.session_id,
                input=request.input,
                trace_id=new_run_id,
            )

            # Mark original run as interrupted
            await self.repo.update_run(
                run_id=run_id,
                status="interrupted",
                last_step_index=last_step_index,
            )

            # Persist user message with new run_id
            await self.repo.create_message(
                session_id=original_run.session_id,
                run_id=new_run.id,
                role="user",
                content=request.input,
            )

            # Stream events - with idempotency awareness
            async for step, event in agent.stream_run(state):
                # Inject run_id into all events
                event.data["run_id"] = new_run.id
                event.data["original_run_id"] = run_id  # For tracking lineage

                if event.event == "step_start" and step is not None:
                    # Check idempotency: skip if this step already succeeded
                    if step.name:
                        idempotency_key = f"{run_id}:{step.step_index}:{step.name}"
                        existing = await self.repo.get_step_by_idempotency_key(
                            idempotency_key
                        )
                        if existing and existing.status == "success":
                            # Skip - step already succeeded in original run
                            continue

                    # Create step record
                    db_step = await self.repo.create_step(
                        session_id=original_run.session_id,
                        run_id=new_run.id,
                        step_index=step.step_index,
                        type=step.type,
                        name=step.name,
                        step_input=step.input,
                        status="running",
                        idempotency_key=f"{new_run.id}:{step.step_index}:{step.name}"
                        if step.name
                        else None,
                    )
                    step.id = db_step.id
                    event.data.pop("id", None)
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == "step_end" and step is not None:
                    event_data = event.data
                    await self.repo.update_step(
                        step_id=step.id,
                        status=event_data.get("status"),
                        output=event_data.get("output"),
                        latency_ms=event_data.get("latency_ms"),
                        error=event_data.get("error"),
                    )
                    event.data["step_id"] = step.id
                    event.data["step_index"] = event_data.get("step_index")

                elif event.event in ("tool_call", "tool_result", "content") and step is not None:
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == "error" and step is not None:
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                yield event.to_sse().encode("utf-8")

                if event.event == "run_end":
                    # Persist assistant message
                    if state.output:
                        await self.repo.create_message(
                            session_id=original_run.session_id,
                            run_id=new_run.id,
                            role="assistant",
                            content=state.output,
                        )

                    # Generate summary
                    current_exchange = [
                        {"role": "user", "content": request.input},
                        {"role": "assistant", "content": state.output or ""},
                    ]
                    new_summary = await self._generate_summary(
                        messages=current_exchange,
                        llm=llm,
                        previous_summary=session.summary,
                    )
                    if new_summary:
                        combined_summary = (
                            (session.summary + "\n" + new_summary)
                            if session.summary
                            else new_summary
                        )
                        await self.repo.update_summary(
                            original_run.session_id, combined_summary
                        )

                    # Mark new run as finished
                    await self.repo.finish_run(
                        run_id=new_run.id,
                        status="success" if state.finished else "error",
                        output=state.output,
                    )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
