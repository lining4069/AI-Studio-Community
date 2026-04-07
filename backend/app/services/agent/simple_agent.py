"""
SimpleAgent - Phase 1 lightweight Agent with 1-loop execution.

LLM → Tool? → Execute → LLM (max 1 iteration)
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from app.services.agent.core import AgentEvent, AgentEventType, AgentState, Step
from app.services.agent.prompt_builder import build_messages, build_system_prompt
from app.services.providers.base import LLMProvider


class SimpleAgent:
    """
    Phase 1 Agent with single-loop LLM tool calling.

    Flow:
    1. Build messages with memory + tools
    2. Call LLM (with tools)
    3. If LLM returns tool call → execute → go to step 2 with result
    4. If no tool call → return response
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: list[Any],
        system_prompt: str | None = None,
        max_loop: int = 1,
        run_id: str | None = None,
    ) -> None:
        """
        Initialize SimpleAgent.

        Args:
            llm: LLM provider instance
            tools: List of Tool instances
            system_prompt: Optional custom system prompt
            max_loop: Maximum execution loop (default 1 for Phase 1)
            run_id: Optional run identifier for SSE event tracking
        """
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_loop = max_loop
        self.run_id = run_id

    def _build_llm_tools(self) -> list[dict]:
        """Convert Tool list to LLM function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.schema,
                },
            }
            for t in self.tools.values()
        ]

    def _event(self, event_type: AgentEventType, data: dict) -> AgentEvent:
        """Create AgentEvent with run_id included in data."""
        data_with_run = {**data, "run_id": self.run_id} if self.run_id else data
        return AgentEvent(event=event_type, data=data_with_run)

    async def _execute_tool_call(self, tool_name: str, arguments: dict | str) -> dict:
        """Execute a tool and return result."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}

        # Parse JSON string arguments if needed (LLM returns string)
        if isinstance(arguments, str):
            import json

            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as e:
                return {"error": f"Invalid JSON arguments: {e}"}

        try:
            result = await tool.run(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return {"error": str(e)}

    async def run(self, state: AgentState) -> AgentState:
        """
        Run the Agent loop.

        Args:
            state: AgentState with user_input and session_id

        Returns:
            Updated AgentState with output and steps
        """
        # Build system prompt
        system_prompt = self.system_prompt or build_system_prompt(
            summary=state.summary,
            tools=self._build_llm_tools(),
        )

        # Build initial messages
        messages = build_messages(
            user_input=state.user_input,
            history=state.messages,
            system_prompt=system_prompt,
        )

        # Loop (max 1 for Phase 1)
        loop_count = 0

        while loop_count < self.max_loop:
            # Note: loop_count increment happens at end of loop or after tool call

            # Record LLM step
            llm_step = Step(type="llm", name=self.llm.provider_name)
            start_time = time.time()

            try:
                # Call LLM with tools
                response = await self.llm.achat(
                    messages=messages,
                    tools=self._build_llm_tools() if self.tools else None,
                )

                # Record latency before potential break
                llm_step.latency_ms = int((time.time() - start_time) * 1000)

                # Check if LLM returned a tool call (OpenAI function calling format)
                if response.get("tool_calls"):
                    # Extract tool call
                    tool_call = response["tool_calls"][0]
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    # Record tool call
                    llm_step.output = {"tool_call": tool_name, "arguments": arguments}
                    llm_step.status = "success"
                    state.add_step(llm_step)

                    # Execute tool
                    tool_step = Step(type="tool", name=tool_name, input=arguments)
                    tool_start = time.time()

                    tool_result = await self._execute_tool_call(tool_name, arguments)
                    tool_step.output = tool_result
                    tool_step.status = (
                        "success" if "error" not in tool_result else "error"
                    )
                    tool_step.latency_ms = int((time.time() - tool_start) * 1000)
                    state.add_step(tool_step)

                    # Feed tool result back to LLM
                    messages.append(
                        {
                            "role": "assistant",
                            "content": response.get("content", ""),
                            "tool_calls": [tool_call],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result),
                        }
                    )

                    # Store in scratchpad
                    state.tool_results[tool_name] = tool_result

                    # After tool execution, loop back for another LLM call
                    # Do NOT increment loop_count - tool execution doesn't count
                    # against max_loop since we need 2 LLM calls when tool is used
                    continue

                else:
                    # Direct response (no tool call)
                    current_output = response.get("content", "")
                    llm_step.output = {"content": current_output}
                    llm_step.status = "success"
                    state.add_step(llm_step)
                    state.output = current_output
                    state.finished = True
                    loop_count += 1
                    break

            except Exception as e:
                logger.error(f"LLM call error: {e}")
                llm_step.status = "error"
                llm_step.error = str(e)
                state.add_step(llm_step)
                state.output = f"Error: {str(e)}"
                state.finished = True
                break

        return state

    async def stream_run(
        self, state: AgentState
    ) -> AsyncGenerator[tuple[Step | None, AgentEvent], None]:
        """
        Streaming version of run() that yields (Step | None, AgentEvent) tuples.

        Uses achat() internally since astream() does not provide structured
        tool call data. Yields proper step events rather than fake tokens.

        Step lifecycle for Phase 2:
        - step_start (Step, event) → service layer INSERTs with status=running
        - step_end (Step, event) → service layer UPDATE with status/output/latency_ms
        - Non-step events (tool_call, tool_result, content) → forwarded to SSE
        - run_end (None, event) → terminal event, no associated Step

        Args:
            state: AgentState with user_input and session_id

        Yields:
            Tuple of (Step, AgentEvent) for SSE streaming
        """
        # Build system prompt
        system_prompt = self.system_prompt or build_system_prompt(
            summary=state.summary,
            tools=self._build_llm_tools(),
        )

        # Build initial messages
        messages = build_messages(
            user_input=state.user_input,
            history=state.messages,
            system_prompt=system_prompt,
        )

        # First LLM call
        llm_step = Step(type="llm", name=self.llm.provider_name)
        start_time = time.time()

        try:
            # Call LLM with tools
            response = await self.llm.achat(
                messages=messages,
                tools=self._build_llm_tools() if self.tools else None,
            )

            llm_step.latency_ms = int((time.time() - start_time) * 1000)

            # Check if LLM returned a tool call
            if response.get("tool_calls"):
                # Extract tool call
                tool_call = response["tool_calls"][0]
                tool_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]

                # Record LLM step with tool call
                llm_step.output = {"tool_call": tool_name, "arguments": arguments}
                llm_step.status = "success"
                state.add_step(llm_step)

                # Yield step_start with llm_step (service layer will INSERT)
                yield (
                    llm_step,
                    self._event(AgentEventType.STEP_START, llm_step.to_dict()),
                )
                yield (
                    None,
                    self._event(
                        AgentEventType.TOOL_CALL,
                        {"tool": tool_name, "arguments": arguments},
                    ),
                )

                # Execute tool
                tool_step = Step(type="tool", name=tool_name, input=arguments)
                tool_start = time.time()

                tool_result = await self._execute_tool_call(tool_name, arguments)

                tool_step.output = tool_result
                tool_step.status = "success" if "error" not in tool_result else "error"
                tool_step.latency_ms = int((time.time() - tool_start) * 1000)
                state.add_step(tool_step)

                # Yield step_start for tool, then tool_result, then step_end
                yield (
                    tool_step,
                    self._event(AgentEventType.STEP_START, tool_step.to_dict()),
                )
                yield (
                    tool_step,
                    self._event(
                        AgentEventType.TOOL_RESULT,
                        {"tool": tool_name, "result": tool_result},
                    ),
                )
                yield (
                    tool_step,
                    self._event(
                        AgentEventType.STEP_END,
                        {
                            "step_index": tool_step.step_index,
                            "status": tool_step.status,
                            "output": tool_step.output,
                            "latency_ms": tool_step.latency_ms,
                            "error": tool_step.error,
                        },
                    ),
                )

                # Feed tool result back to LLM for final response
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": [tool_call],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": str(tool_result),
                    }
                )

                # Store in scratchpad
                state.tool_results[tool_name] = tool_result

                # Get final LLM response after tool execution
                final_llm_step = Step(type="llm", name=self.llm.provider_name)
                final_start = time.time()
                final_response = await self.llm.achat(messages=messages)
                final_llm_step.latency_ms = int((time.time() - final_start) * 1000)
                final_llm_step.output = {"content": final_response.get("content", "")}
                final_llm_step.status = "success"
                state.add_step(final_llm_step)

                # Yield step_start, content, then step_end for final LLM
                yield (
                    final_llm_step,
                    self._event(AgentEventType.STEP_START, final_llm_step.to_dict()),
                )
                yield (
                    final_llm_step,
                    self._event(
                        AgentEventType.CONTENT,
                        {"content": final_response.get("content", "")},
                    ),
                )
                yield (
                    final_llm_step,
                    self._event(
                        AgentEventType.STEP_END,
                        {
                            "step_index": final_llm_step.step_index,
                            "status": final_llm_step.status,
                            "output": final_llm_step.output,
                            "latency_ms": final_llm_step.latency_ms,
                        },
                    ),
                )

                # Set final output and state
                state.output = final_response.get("content", "")
                state.finished = True

                # CRITICAL: Yield run_end with output included
                yield (
                    None,
                    self._event(
                        AgentEventType.RUN_END,
                        {
                            "output": state.output,
                            "summary": state.summary,
                        },
                    ),
                )

            else:
                # Direct response (no tool call)
                llm_step.output = {"content": response.get("content", "")}
                llm_step.status = "success"
                state.add_step(llm_step)

                # Set state output before yielding events
                state.output = response.get("content", "")
                state.finished = True

                # Yield step_start, content, then step_end
                yield (
                    llm_step,
                    self._event(AgentEventType.STEP_START, llm_step.to_dict()),
                )
                yield (
                    llm_step,
                    self._event(
                        AgentEventType.CONTENT, {"content": response.get("content", "")}
                    ),
                )
                yield (
                    llm_step,
                    self._event(
                        AgentEventType.STEP_END,
                        {
                            "step_index": llm_step.step_index,
                            "status": llm_step.status,
                            "output": llm_step.output,
                            "latency_ms": llm_step.latency_ms,
                        },
                    ),
                )

                # CRITICAL: Yield run_end with output included
                yield (
                    None,
                    self._event(
                        AgentEventType.RUN_END,
                        {
                            "output": state.output,
                            "summary": state.summary,
                        },
                    ),
                )

        except Exception as e:
            logger.error(f"LLM call error: {e}")
            llm_step.status = "error"
            llm_step.error = str(e)
            state.add_step(llm_step)
            yield (llm_step, self._event(AgentEventType.ERROR, {"error": str(e)}))
            yield (
                llm_step,
                self._event(
                    AgentEventType.STEP_END,
                    {
                        "step_index": llm_step.step_index,
                        "status": llm_step.status,
                        "output": None,
                        "latency_ms": llm_step.latency_ms,
                        "error": llm_step.error,
                    },
                ),
            )
            # CRITICAL: Yield run_end with output included (even on error, output might have partial content)
            yield (
                None,
                self._event(
                    AgentEventType.RUN_END,
                    {
                        "output": state.output,
                        "summary": state.summary,
                    },
                ),
            )
            return
