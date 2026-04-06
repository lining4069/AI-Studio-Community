"""
SimpleAgent - Phase 1 lightweight Agent with 1-loop execution.

LLM → Tool? → Execute → LLM (max 1 iteration)
"""
import time
from typing import Any, AsyncGenerator

from loguru import logger

from app.services.agent.core import AgentEvent, AgentState, Step
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
    ) -> None:
        """
        Initialize SimpleAgent.

        Args:
            llm: LLM provider instance
            tools: List of Tool instances
            system_prompt: Optional custom system prompt
            max_loop: Maximum execution loop (default 1 for Phase 1)
        """
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_loop = max_loop

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

    async def _execute_tool_call(
        self, tool_name: str, arguments: dict
    ) -> dict:
        """Execute a tool and return result."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}

        try:
            result = await tool.run(arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return {"error": str(e)}

    async def run(
        self, state: AgentState
    ) -> AgentState:
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
                    tool_step.status = "success" if "error" not in tool_result else "error"
                    tool_step.latency_ms = int((time.time() - tool_start) * 1000)
                    state.add_step(tool_step)

                    # Feed tool result back to LLM
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": [tool_call],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": str(tool_result),
                    })

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
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Streaming version of run() that yields SSE events.

        Uses achat() internally since astream() does not provide structured
        tool call data. Yields proper step events rather than fake tokens.

        Args:
            state: AgentState with user_input and session_id

        Yields:
            AgentEvent for SSE streaming
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

                yield AgentEvent(event="step_start", data=llm_step.to_dict())
                yield AgentEvent(
                    event="tool_call",
                    data={"tool": tool_name, "arguments": arguments},
                )

                # Execute tool
                tool_step = Step(type="tool", name=tool_name, input=arguments)
                tool_start = time.time()

                tool_result = await self._execute_tool_call(tool_name, arguments)

                tool_step.output = tool_result
                tool_step.status = "success" if "error" not in tool_result else "error"
                tool_step.latency_ms = int((time.time() - tool_start) * 1000)
                state.add_step(tool_step)

                # Yield tool result event
                yield AgentEvent(
                    event="tool_result",
                    data={"tool": tool_name, "result": tool_result},
                )

                # Feed tool result back to LLM for final response
                messages.append({
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": [tool_call],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(tool_result),
                })

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

                yield AgentEvent(event="content", data={"content": final_response.get("content", "")})

            else:
                # Direct response (no tool call)
                llm_step.output = {"content": response.get("content", "")}
                llm_step.status = "success"
                state.add_step(llm_step)
                yield AgentEvent(event="step_start", data=llm_step.to_dict())
                yield AgentEvent(event="content", data={"content": response.get("content", "")})

        except Exception as e:
            logger.error(f"LLM call error: {e}")
            llm_step.status = "error"
            llm_step.error = str(e)
            state.add_step(llm_step)
            yield AgentEvent(event="error", data={"error": str(e)})

        yield AgentEvent(event="run_end", data={"summary": state.summary})
