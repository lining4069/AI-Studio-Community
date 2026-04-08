"""Agent service - business logic and orchestration."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse
from loguru import logger

from app.common.exceptions import NotFoundException
from app.modules.agent.agent_factory import create_agent
from app.modules.agent.config_loader import AgentConfigLoader
from app.modules.agent.domain import DomainConfig
from app.modules.agent.models import AgentSession
from app.modules.agent.repository import AgentRepository
from app.modules.agent.schema import (
    AgentRunRequest,
    AgentSessionCreate,
    AgentSessionResponse,
)
from app.modules.agent.tool_builder import ToolBuilder
from app.modules.llm_model.repository import LlmModelRepository
from app.services.agent.core import AgentEventType, AgentState
from app.services.providers.model_factory import create_llm


class AgentService:
    """
    Business logic for Agent system.

    Handles session management, agent execution, and SSE streaming.

    Phase 4: Integrates AgentConfig for persistent configuration,
    ToolBuilder for tool construction, and snapshot for run reproducibility.
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

        Phase 4: Supports AgentConfig via session.config_id.

        Returns full result dict with output, summary, steps.
        """
        session = await self.get_session(session_id, user_id)

        # Load messages for context
        db_messages = await self.repo.get_messages(session_id)
        history = [{"role": m.role, "content": m.content} for m in db_messages]

        # Create LLM
        llm = await self._get_llm_for_session(session, user_id)

        # Phase 4: Load config and build tools
        domain_config: DomainConfig | None = None
        if session.config_id:
            config_loader = AgentConfigLoader(self.repo.db)
            domain_config = await config_loader.load(session.config_id, user_id)

        rag_service = None
        tool_builder = ToolBuilder(rag_service=rag_service)
        tools, warnings = await tool_builder.build(domain_config)

        agent_type = domain_config.agent_type if domain_config else "simple"

        # Build initial state
        state = AgentState(
            session_id=session_id,
            user_input=request.input,
            messages=history,
            summary=session.summary,
        )

        # Run agent via factory
        agent = create_agent(
            agent_type=agent_type,
            tools=tools,
            llm=llm,
            run_id=None,
            config=domain_config,
        )
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
                step_input=step.input,
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

        Phase 3: Supports MCP tools via mcp_server_ids in request.

        Phase 4: Supports AgentConfig via session.config_id.
        - Loads config from AgentConfigLoader
        - Builds tools via ToolBuilder
        - Saves snapshot to AgentRun.config_snapshot for reproducibility

        Returns StreamingResponse with event stream.
        """
        session = await self.get_session(session_id, user_id)

        # Load messages for context
        db_messages = await self.repo.get_messages(session_id)
        history = [{"role": m.role, "content": m.content} for m in db_messages]

        # Create LLM
        llm = await self._get_llm_for_session(session, user_id)

        # Phase 4: Load config and build tools
        domain_config: DomainConfig | None = None
        if session.config_id:
            config_loader = AgentConfigLoader(self.repo.db)
            domain_config = await config_loader.load(session.config_id, user_id)

        # Build tools via ToolBuilder
        rag_service = None  # TODO: Create RAG service from knowledge_base
        tool_builder = ToolBuilder(rag_service=rag_service)
        tools, warnings = await tool_builder.build(domain_config)
        if warnings:
            logger.warning(f"Tool load warnings for session {session_id}: {warnings}")

        # Determine agent type from config or default to simple
        agent_type = domain_config.agent_type if domain_config else "simple"

        # Build initial state
        state = AgentState(
            session_id=session_id,
            user_input=request.input,
            messages=history,
            summary=session.summary,
        )

        # Generate run_id for SSE event tracking
        run_id = uuid.uuid4().hex

        # Run streaming agent via factory
        agent = create_agent(
            agent_type=agent_type,
            tools=tools,
            llm=llm,
            run_id=run_id,
            config=domain_config,
        )

        async def event_generator() -> AsyncGenerator[bytes, None]:
            # Create run immediately (Phase 2: request start = run creation)
            run = await self.repo.create_run(
                session_id=session_id,
                input=request.input,
                trace_id=run_id,
            )

            # Phase 4: Save config snapshot to run BEFORE execution
            # This ensures run reproducibility even if config changes later
            if domain_config:
                await self.repo.update_run_snapshot(run.id, domain_config.to_snapshot())

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
                        step_index=step.step_index or 0,
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
                    # LLM completed and triggered a tool call - mark LLM step as success
                    # This fixes the missing step_end for LLM steps that use tools
                    step.status = "success"
                    step.output = {
                        "tool_call": event.data.get("tool"),
                        "arguments": event.data.get("arguments"),
                    }
                    await self.repo.update_step(
                        step_id=step.id,
                        status="success",
                        output=step.output,
                    )
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

        # 5. Create LLM
        llm = await self._get_llm_for_session(session, user_id)

        # 6. Phase 4: Load config from snapshot for reproducibility
        #    Use config_snapshot from original run (frozen at run start)
        domain_config: DomainConfig | None = None
        if original_run.config_snapshot:
            domain_config = DomainConfig.from_snapshot(original_run.config_snapshot)

        # 7. Build tools via ToolBuilder (same as stream_agent)
        rag_service = None
        tool_builder = ToolBuilder(rag_service=rag_service)
        tools, warnings = await tool_builder.build(domain_config)
        if warnings:
            logger.warning(f"Tool load warnings for resume run {run_id}: {warnings}")

        # 8. Determine agent type from config
        agent_type = domain_config.agent_type if domain_config else "simple"

        # 9. Build initial state from successful steps + summary
        #    Skip all successful steps (they're already in history/scratchpad)
        last_step_index = successful_steps[-1].step_index if successful_steps else -1

        state = AgentState(
            session_id=original_run.session_id,
            user_input=request.input,
            messages=history,
            summary=session.summary,
            tool_results=tool_results,
        )

        # 10. Generate new run_id for SSE tracking
        new_run_id = uuid.uuid4().hex

        # 11. Run streaming agent via factory
        agent = create_agent(
            agent_type=agent_type,
            tools=tools,
            llm=llm,
            run_id=new_run_id,
            config=domain_config,
        )

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
                # Handle RUN_END specially: persist BEFORE yield
                # This ensures data is saved even if client disconnects
                if event.event == AgentEventType.RUN_END:
                    # CRITICAL: All persistence MUST happen before yield
                    # 1. Persist assistant message
                    if state.output:
                        await self.repo.create_message(
                            session_id=original_run.session_id,
                            run_id=new_run.id,
                            role="assistant",
                            content=state.output,
                        )

                    # 2. Generate summary
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

                    # 3. Mark new run as finished
                    await self.repo.finish_run(
                        run_id=new_run.id,
                        status="success" if state.finished else "error",
                        output=state.output,
                    )

                    # 4. Update event data with summary
                    event.data["summary"] = new_summary or session.summary
                    event.data["run_id"] = new_run.id
                    event.data["original_run_id"] = run_id

                    # 5. Yield RUN_END SSE
                    yield event.to_sse().encode("utf-8")
                    continue

                # Inject run_id into all events
                event.data["run_id"] = new_run.id
                event.data["original_run_id"] = run_id  # For tracking lineage

                if event.event == AgentEventType.STEP_START and step is not None:
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

                elif event.event == AgentEventType.STEP_END and step is not None:
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
                    # LLM completed and triggered a tool call - mark LLM step as success
                    step.status = "success"
                    step.output = {
                        "tool_call": event.data.get("tool"),
                        "arguments": event.data.get("arguments"),
                    }
                    await self.repo.update_step(
                        step_id=step.id,
                        status="success",
                        output=step.output,
                    )
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif (
                    event.event
                    in (
                        AgentEventType.TOOL_RESULT,
                        AgentEventType.CONTENT,
                    )
                    and step is not None
                ):
                    event.data["step_id"] = step.id
                    event.data["step_index"] = step.step_index

                elif event.event == AgentEventType.ERROR and step is not None:
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

    # =========================================================================
    # AgentConfig Service (Phase 4)
    # =========================================================================

    async def create_config(
        self,
        user_id: int,
        name: str,
        description: str | None = None,
        llm_model_id: str | None = None,
        agent_type: str = "simple",
        max_loop: int = 5,
        system_prompt: str | None = None,
        enabled: bool = True,
    ) -> dict:
        """Create a new agent config."""
        config = await self.repo.create_config(
            user_id=user_id,
            name=name,
            description=description,
            llm_model_id=llm_model_id,
            agent_type=agent_type,
            max_loop=max_loop,
            system_prompt=system_prompt,
            enabled=enabled,
        )
        return {
            "id": config.id,
            "user_id": config.user_id,
            "name": config.name,
            "description": config.description,
            "llm_model_id": config.llm_model_id,
            "agent_type": config.agent_type,
            "max_loop": config.max_loop,
            "system_prompt": config.system_prompt,
            "enabled": config.enabled,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }

    async def get_config(self, config_id: str, user_id: int) -> dict | None:
        """Get agent config by ID."""
        config = await self.repo.get_config(config_id, user_id)
        if not config:
            return None
        return {
            "id": config.id,
            "user_id": config.user_id,
            "name": config.name,
            "description": config.description,
            "llm_model_id": config.llm_model_id,
            "agent_type": config.agent_type,
            "max_loop": config.max_loop,
            "system_prompt": config.system_prompt,
            "enabled": config.enabled,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }

    async def list_configs(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """List agent configs for user (paginated)."""
        configs, total = await self.repo.list_configs(
            user_id, page=page, page_size=page_size
        )
        return [
            {
                "id": c.id,
                "user_id": c.user_id,
                "name": c.name,
                "description": c.description,
                "llm_model_id": c.llm_model_id,
                "agent_type": c.agent_type,
                "max_loop": c.max_loop,
                "system_prompt": c.system_prompt,
                "enabled": c.enabled,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in configs
        ], total

    async def update_config(
        self,
        config_id: str,
        user_id: int,
        name: str | None = None,
        description: str | None = None,
        llm_model_id: str | None = None,
        agent_type: str | None = None,
        max_loop: int | None = None,
        system_prompt: str | None = None,
        enabled: bool | None = None,
    ) -> dict | None:
        """Update agent config."""
        config = await self.repo.update_config(
            config_id=config_id,
            user_id=user_id,
            name=name,
            description=description,
            llm_model_id=llm_model_id,
            agent_type=agent_type,
            max_loop=max_loop,
            system_prompt=system_prompt,
            enabled=enabled,
        )
        if not config:
            return None
        return {
            "id": config.id,
            "user_id": config.user_id,
            "name": config.name,
            "description": config.description,
            "llm_model_id": config.llm_model_id,
            "agent_type": config.agent_type,
            "max_loop": config.max_loop,
            "system_prompt": config.system_prompt,
            "enabled": config.enabled,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }

    async def delete_config(self, config_id: str, user_id: int) -> bool:
        """Delete agent config."""
        return await self.repo.delete_config(config_id, user_id)

    # Config Tools
    async def add_config_tool(
        self,
        config_id: str,
        tool_name: str,
        tool_config: dict | None = None,
        enabled: bool = True,
    ) -> dict:
        """Add a tool to a config."""
        tool = await self.repo.add_config_tool(
            config_id=config_id,
            tool_name=tool_name,
            tool_config=tool_config,
            enabled=enabled,
        )
        return {
            "id": tool.id,
            "config_id": tool.config_id,
            "tool_name": tool.tool_name,
            "tool_config": tool.tool_config,
            "enabled": tool.enabled,
        }

    async def update_config_tool(
        self,
        tool_id: int,
        tool_config: dict | None = None,
        enabled: bool | None = None,
    ) -> dict | None:
        """Update a config tool."""
        tool = await self.repo.update_config_tool(
            tool_id=tool_id,
            tool_config=tool_config,
            enabled=enabled,
        )
        if not tool:
            return None
        return {
            "id": tool.id,
            "config_id": tool.config_id,
            "tool_name": tool.tool_name,
            "tool_config": tool.tool_config,
            "enabled": tool.enabled,
        }

    async def delete_config_tool(self, tool_id: int) -> bool:
        """Delete a config tool."""
        return await self.repo.delete_config_tool(tool_id)

    async def get_config_tools(self, config_id: str) -> list[dict]:
        """Get all tools for a config."""
        tools = await self.repo.get_config_tools(config_id)
        return [
            {
                "id": t.id,
                "config_id": t.config_id,
                "tool_name": t.tool_name,
                "tool_config": t.tool_config,
                "enabled": t.enabled,
            }
            for t in tools
        ]

    # Config MCP Servers
    async def add_config_mcp_server(
        self,
        config_id: str,
        mcp_server_id: str,
    ) -> dict:
        """Link an MCP server to a config."""
        link = await self.repo.add_config_mcp_server(
            config_id=config_id,
            mcp_server_id=mcp_server_id,
        )
        return {
            "id": link.id,
            "config_id": link.config_id,
            "mcp_server_id": link.mcp_server_id,
        }

    async def delete_config_mcp_server(self, link_id: int) -> bool:
        """Unlink an MCP server from a config."""
        return await self.repo.delete_config_mcp_server(link_id)

    async def get_config_mcp_links(self, config_id: str) -> list[dict]:
        """Get all MCP server links for a config."""
        links = await self.repo.get_config_mcp_links(config_id)
        return [
            {
                "id": link.id,
                "config_id": link.config_id,
                "mcp_server_id": link.mcp_server_id,
            }
            for link in links
        ]

    # Config KB Links
    async def add_config_kb(
        self,
        config_id: str,
        kb_id: str,
        kb_config: dict | None = None,
    ) -> dict:
        """Link a knowledge base to a config."""
        link = await self.repo.add_config_kb(
            config_id=config_id,
            kb_id=kb_id,
            kb_config=kb_config,
        )
        return {
            "id": link.id,
            "config_id": link.config_id,
            "kb_id": link.kb_id,
            "kb_config": link.kb_config,
        }

    async def delete_config_kb(self, link_id: int) -> bool:
        """Unlink a knowledge base from a config."""
        return await self.repo.delete_config_kb(link_id)

    async def get_config_kb_links(self, config_id: str) -> list[dict]:
        """Get all KB links for a config."""
        links = await self.repo.get_config_kb_links(config_id)
        return [
            {
                "id": link.id,
                "config_id": link.config_id,
                "kb_id": link.kb_id,
                "kb_config": link.kb_config,
            }
            for link in links
        ]

    # =========================================================================
    # MCP Server Service (Phase 4)
    # =========================================================================

    async def create_mcp_server(
        self,
        user_id: int,
        name: str,
        url: str,
        headers: dict | None = None,
        transport: str = "streamable_http",
        enabled: bool = True,
    ) -> dict:
        """Create a new MCP server."""
        server = await self.repo.create_mcp_server(
            user_id=user_id,
            name=name,
            url=url,
            headers=headers,
            transport=transport,
            enabled=enabled,
        )
        return {
            "id": server.id,
            "user_id": server.user_id,
            "name": server.name,
            "url": server.url,
            "headers": server.headers,
            "transport": server.transport,
            "enabled": server.enabled,
            "created_at": server.created_at.isoformat(),
            "updated_at": server.updated_at.isoformat(),
        }

    async def get_mcp_server(self, server_id: str, user_id: int) -> dict | None:
        """Get MCP server by ID."""
        server = await self.repo.get_mcp_server(server_id, user_id)
        if not server:
            return None
        return {
            "id": server.id,
            "user_id": server.user_id,
            "name": server.name,
            "url": server.url,
            "headers": server.headers,
            "transport": server.transport,
            "enabled": server.enabled,
            "created_at": server.created_at.isoformat(),
            "updated_at": server.updated_at.isoformat(),
        }

    async def list_mcp_servers(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """List MCP servers for user."""
        servers = await self.repo.get_mcp_servers(user_id=user_id)
        return [
            {
                "id": s.id,
                "user_id": s.user_id,
                "name": s.name,
                "url": s.url,
                "headers": s.headers,
                "transport": s.transport,
                "enabled": s.enabled,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in servers
        ], len(servers)

    async def update_mcp_server(
        self,
        server_id: str,
        user_id: int,
        name: str | None = None,
        url: str | None = None,
        headers: dict | None = None,
        transport: str | None = None,
        enabled: bool | None = None,
    ) -> dict | None:
        """Update MCP server."""
        server = await self.repo.update_mcp_server(
            server_id=server_id,
            user_id=user_id,
            name=name,
            url=url,
            headers=headers,
            transport=transport,
            enabled=enabled,
        )
        if not server:
            return None
        return {
            "id": server.id,
            "user_id": server.user_id,
            "name": server.name,
            "url": server.url,
            "headers": server.headers,
            "transport": server.transport,
            "enabled": server.enabled,
            "created_at": server.created_at.isoformat(),
            "updated_at": server.updated_at.isoformat(),
        }

    async def delete_mcp_server(self, server_id: str, user_id: int) -> bool:
        """Delete MCP server."""
        return await self.repo.delete_mcp_server(server_id, user_id)

    async def test_mcp_server(self, server_id: str, user_id: int) -> dict:
        """Test MCP server connection."""
        server = await self.repo.get_mcp_server(server_id, user_id)
        if not server:
            return {"success": False, "message": "Server not found", "tools_count": 0}

        try:
            from app.modules.agent.mcp.session import create_session
            from app.modules.agent.mcp.exceptions import MCPError

            async with create_session(
                transport=server.transport,
                url=server.url,
                command=server.command,
                args=server.args,
                env=server.env,
                cwd=server.cwd,
                headers=server.headers,
            ) as session:
                result = await session.list_tools()

            return {
                "success": True,
                "message": "Connection successful",
                "tools_count": len(result.tools),
            }
        except MCPError as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "tools_count": 0,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "tools_count": 0,
            }

    # =========================================================================
    # Session Config Binding (Phase 4)
    # =========================================================================

    async def update_session_config(
        self, session_id: str, user_id: int, config_id: str | None
    ) -> None:
        """Update session's config_id binding."""
        await self.get_session(session_id, user_id)  # Verify ownership
        await self.repo.update_session_config(session_id, config_id)

    # =========================================================================
    # Builtin Tools (Phase 4)
    # =========================================================================

    async def get_builtin_tools(self) -> list[dict]:
        """Get all available built-in tools."""
        return [
            {
                "name": "calculator",
                "description": "数学计算工具",
                "has_config": False,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "数学表达式"}
                    },
                    "required": ["expression"],
                },
            },
            {
                "name": "datetime",
                "description": "当前日期时间",
                "has_config": False,
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "websearch",
                "description": "网络搜索 (Tavily)",
                "has_config": True,
                "config_schema": {
                    "api_key": {"type": "string"},
                    "search_depth": {"type": "string", "enum": ["basic", "advanced"]},
                },
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"],
                },
            },
        ]

    # =========================================================================
    # Resolved Tools Debug (Phase 4)
    # =========================================================================

    async def get_resolved_tools(
        self, config_id: str, user_id: int
    ) -> tuple[list[dict], list[str]]:
        """
        Get resolved tool list for a config (for debugging).

        Returns:
            Tuple of (tools, warnings) showing what would be loaded.
        """
        config_loader = AgentConfigLoader(self.repo.db)
        domain_config = await config_loader.load(config_id, user_id)
        if not domain_config:
            return [], ["Config not found"]

        rag_service = None
        tool_builder = ToolBuilder(rag_service=rag_service)
        tools, warnings = await tool_builder.build(domain_config)

        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ], warnings
