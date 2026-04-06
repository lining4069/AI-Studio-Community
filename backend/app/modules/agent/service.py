"""Agent service - business logic and orchestration."""
import asyncio
import json
import uuid
from typing import Any, AsyncGenerator

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
from app.services.agent.core import AgentEvent, AgentState
from app.services.agent.factories import create_agent_tools
from app.services.agent.simple_agent import SimpleAgent
from app.services.providers.model_factory import create_llm
from app.modules.llm_model.repository import LlmModelRepository


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

    async def get_session(
        self, session_id: str, user_id: int
    ) -> AgentSession:
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
        messages = await self.repo.get_messages(session_id, limit)
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    async def get_steps(
        self, session_id: str, user_id: int
    ) -> list[dict]:
        """Get execution steps for a session."""
        await self.get_session(session_id, user_id)
        steps = await self.repo.get_steps(session_id)
        return [
            {
                "id": s.id,
                "session_id": s.session_id,
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
                step_index=step.step_index,
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
        Run agent with SSE streaming.

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
            # Persist user message first
            await self.repo.create_message(
                session_id=session_id,
                role="user",
                content=request.input,
            )

            final_state = None
            async for event in agent.stream_run(state):
                final_state = event.state
                yield event.to_sse().encode("utf-8")

            # Persist assistant response after streaming completes
            if final_state and final_state.output:
                await self.repo.create_message(
                    session_id=session_id,
                    role="assistant",
                    content=final_state.output,
                )

            # Persist all steps after streaming completes (BUG FIX)
            if final_state and final_state.steps:
                for step in final_state.steps:
                    await self.repo.create_step(
                        session_id=session_id,
                        step_index=step.step_index,
                        type=step.type,
                        name=step.name,
                        input=step.input,
                        output=step.output,
                        status=step.status,
                        error=step.error,
                        latency_ms=step.latency_ms,
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

    async def _get_llm_for_session(
        self, session: AgentSession, user_id: int
    ):
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
    ) -> str | None:
        """
        Generate conversation summary using LLM.

        Called when conversation ends or periodically for long sessions.
        """
        if len(messages) < 3:
            return None  # Not enough context for summary

        try:
            # Build summary prompt
            summary_prompt = (
                "Summarize the following conversation concisely in 2-3 sentences. "
                "Focus on the main topics discussed and any key conclusions.\n\n"
            )
            for msg in messages[-10:]:  # Last 10 messages
                summary_prompt += f"{msg['role']}: {msg['content'][:200]}\n"

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
