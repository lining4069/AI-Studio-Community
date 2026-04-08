"""
ReactAgent - Multi-step ReAct Agent with Think → Action → Observe loop.

LLM → Think → Decision (Tool?) → Execute → Observe → ... → Response

Phase 3 Ready Protocol:
- Step types: llm_thought, llm_decision, tool, llm_observation, llm_response
- Each STEP_START has exactly one STEP_END
- TOOL_CALL belongs to llm_decision step (step_id required)
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from app.services.agent.adapters import to_openai_tools
from app.services.agent.core import (
    AgentEvent,
    AgentEventType,
    AgentState,
    Step,
    StepType,
)
from app.services.agent.prompt_builder import build_messages, build_system_prompt
from app.services.providers.base import LLMProvider


class ReactAgent:
    """
    Phase 3 Agent with multi-step ReAct loop.

    Flow (per iteration):
    1. LLM Think (llm_thought) → input={messages, tools}, output={thought}
    2. LLM Decision (llm_decision) → input={messages, tools, thought}, output={decision}
    3. If decision is tool_call:
       a. Execute tool (tool) → input={arguments}, output={result}
       b. LLM Observe (llm_observation) → input={tool_result}, output={observation}
       c. Loop back to step 1
    4. If decision is response:
       a. LLM Response (llm_response) → input={messages}, output={content}

    Phase 3 Ready Protocol:
    - llm_thought: input={messages, tools}, output={thought}
    - llm_decision: input={messages, tools, thought}, output={decision: {type, tool, arguments}}
    - tool: input={arguments}, output={result} or {error}, role="tool"
    - llm_observation: input={tool_result}, output={observation}
    - llm_response: input={messages}, output={content}
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: list[Any],
        system_prompt: str | None = None,
        max_loop: int = 5,
        run_id: str | None = None,
    ) -> None:
        """
        Initialize ReactAgent.

        Args:
            llm: LLM provider instance
            tools: List of Tool instances
            system_prompt: Optional custom system prompt
            max_loop: Maximum ReAct iterations (default 5)
            run_id: Optional run identifier for SSE event tracking
        """
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_loop = max_loop
        self.run_id = run_id

    def _build_llm_tools(self) -> list[dict]:
        """Convert Tool list to OpenAI function calling format via adapter."""
        specs = [t.to_spec() for t in self.tools.values()]
        return to_openai_tools(specs)

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
        Run the ReactAgent loop (non-streaming, for testing/debugging).

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

        # ReAct loop
        loop_count = 0
        last_thought = None

        while loop_count < self.max_loop:
            # Step 1: LLM Think (llm_thought)
            thought_step = Step(
                type=StepType.LLM_THOUGHT,
                name=self.llm.provider_name,
                input={"messages": messages, "tools": self._build_llm_tools()},
            )
            thought_start = time.time()

            try:
                thought_response = await self.llm.ainvoke(
                    prompt=f"{system_prompt}\n\n{self._get_thought_prompt()}",
                )
                thought_text = thought_response.get("content", "")
                last_thought = thought_text

                thought_step.output = {"thought": thought_text}
                thought_step.status = "success"
                thought_step.latency_ms = int((time.time() - thought_start) * 1000)
                state.add_step(thought_step)

                # Add thought to messages
                messages.append(
                    {"role": "assistant", "content": f"Thought: {thought_text}"}
                )

            except Exception as e:
                logger.error(f"LLM think error: {e}")
                thought_step.status = "error"
                thought_step.error = str(e)
                state.add_step(thought_step)
                state.output = f"Error: {str(e)}"
                state.finished = True
                break

            # Step 2: LLM Decision (llm_decision)
            decision_step = Step(
                type=StepType.LLM_DECISION,
                name=self.llm.provider_name,
                input={
                    "messages": messages,
                    "tools": self._build_llm_tools(),
                    "thought": last_thought,
                },
            )
            decision_start = time.time()

            try:
                decision_response = await self.llm.achat(
                    messages=messages,
                    tools=self._build_llm_tools() if self.tools else None,
                )
                decision_step.latency_ms = int((time.time() - decision_start) * 1000)

                # Check if LLM returned a tool call
                if decision_response.get("tool_calls"):
                    tool_call = decision_response["tool_calls"][0]
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    # Parse arguments if string
                    if isinstance(arguments, str):
                        import json

                        arguments = json.loads(arguments)

                    decision_step.output = {
                        "decision": {
                            "type": "tool_call",
                            "tool": tool_name,
                            "arguments": arguments,
                        }
                    }
                    decision_step.status = "success"
                    state.add_step(decision_step)

                    # Add decision to messages
                    messages.append(
                        {
                            "role": "assistant",
                            "content": decision_response.get("content", ""),
                            "tool_calls": [tool_call],
                        }
                    )

                    # Step 3a: Execute Tool
                    tool_step = Step(
                        type=StepType.TOOL,
                        name=tool_name,
                        input={"arguments": arguments},
                        role="tool",
                    )
                    tool_start = time.time()

                    tool_result = await self._execute_tool_call(tool_name, arguments)
                    tool_step.output = tool_result
                    tool_step.status = (
                        "success" if "error" not in tool_result else "error"
                    )
                    tool_step.latency_ms = int((time.time() - tool_start) * 1000)
                    state.add_step(tool_step)

                    state.tool_results[tool_name] = tool_result

                    # Add tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result),
                        }
                    )

                    # Step 3b: LLM Observe (llm_observation)
                    if tool_step.status == "success":
                        observation_step = Step(
                            type=StepType.LLM_OBSERVATION,
                            name=self.llm.provider_name,
                            input={"tool_result": tool_result},
                        )
                        observation_start = time.time()

                        try:
                            # Generate observation based on tool result
                            observation_text = (
                                f"Observation: I used {tool_name} and got {tool_result}"
                            )
                            observation_step.output = {"observation": observation_text}
                            observation_step.status = "success"
                        except Exception as e:
                            logger.error(f"LLM observation error: {e}")
                            observation_step.status = "error"
                            observation_step.error = str(e)

                        observation_step.latency_ms = int(
                            (time.time() - observation_start) * 1000
                        )
                        state.add_step(observation_step)

                    # Loop back for next iteration
                    loop_count += 1
                    continue

                else:
                    # No tool call - final response
                    decision_step.type = StepType.LLM_RESPONSE
                    decision_step.output = {
                        "content": decision_response.get("content", "")
                    }
                    decision_step.status = "success"
                    state.add_step(decision_step)
                    state.output = decision_response.get("content", "")
                    state.finished = True
                    break

            except Exception as e:
                logger.error(f"LLM decision error: {e}")
                decision_step.status = "error"
                decision_step.error = str(e)
                state.add_step(decision_step)
                state.output = f"Error: {str(e)}"
                state.finished = True
                break

        return state

    async def stream_run(
        self, state: AgentState
    ) -> AsyncGenerator[tuple[Step | None, AgentEvent], None]:
        """
        Streaming version of run() that yields (Step | None, AgentEvent) tuples.

        Phase 3 Ready Protocol:
        - STEP_START → INSERT step (status=running)
        - TOOL_CALL → belongs to llm_decision step (step_id required)
        - STEP_END → UPDATE step (status/output/latency)
        - Each STEP_START has exactly one STEP_END
        - run_end → terminal event

        Step sequence per ReAct iteration:
        1. llm_thought: STEP_START → THOUGHT → STEP_END
        2. llm_decision: STEP_START → TOOL_CALL → STEP_END
        3. tool: STEP_START → TOOL_RESULT → STEP_END
        4. llm_observation: STEP_START → OBSERVATION → STEP_END
        (loop back to 1 or go to 5)
        5. llm_response: STEP_START → CONTENT → STEP_END

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

        # ReAct loop
        loop_count = 0
        last_thought = None

        while loop_count < self.max_loop:
            # =================================================================
            # Step 1: LLM Think (llm_thought)
            # =================================================================
            thought_step = Step(
                type=StepType.LLM_THOUGHT,
                name=self.llm.provider_name,
                input={"messages": messages, "tools": self._build_llm_tools()},
            )
            thought_start = time.time()

            try:
                thought_response = await self.llm.ainvoke(
                    prompt=f"{system_prompt}\n\n{self._get_thought_prompt()}",
                )
                thought_text = thought_response.get("content", "")
                last_thought = thought_text

                thought_step.latency_ms = int((time.time() - thought_start) * 1000)
                thought_step.output = {"thought": thought_text}
                thought_step.status = "success"
                state.add_step(thought_step)

            except Exception as e:
                logger.error(f"LLM think error: {e}")
                thought_step.status = "error"
                thought_step.error = str(e)
                thought_step.latency_ms = int((time.time() - thought_start) * 1000)
                state.add_step(thought_step)
                yield (
                    thought_step,
                    self._event(AgentEventType.ERROR, {"error": str(e)}),
                )
                yield (
                    None,
                    self._event(
                        AgentEventType.RUN_END,
                        {"output": state.output, "summary": state.summary},
                    ),
                )
                return

            # Yield STEP_START for llm_thought
            yield (
                thought_step,
                self._event(AgentEventType.STEP_START, thought_step.to_dict()),
            )

            # Yield THOUGHT
            yield (
                thought_step,
                self._event(AgentEventType.THOUGHT, {"thought": thought_text}),
            )

            # Yield STEP_END for llm_thought
            yield (
                thought_step,
                self._event(
                    AgentEventType.STEP_END,
                    {
                        "step_index": thought_step.step_index,
                        "status": thought_step.status,
                        "output": thought_step.output,
                        "latency_ms": thought_step.latency_ms,
                    },
                ),
            )

            # Add thought to messages
            messages.append(
                {"role": "assistant", "content": f"Thought: {thought_text}"}
            )

            # =================================================================
            # Step 2: LLM Decision (llm_decision)
            # =================================================================
            decision_step = Step(
                type=StepType.LLM_DECISION,
                name=self.llm.provider_name,
                input={
                    "messages": messages,
                    "tools": self._build_llm_tools(),
                    "thought": last_thought,
                },
            )
            decision_start = time.time()

            try:
                decision_response = await self.llm.achat(
                    messages=messages,
                    tools=self._build_llm_tools() if self.tools else None,
                )
                decision_step.latency_ms = int((time.time() - decision_start) * 1000)

                # Check if LLM returned a tool call
                if decision_response.get("tool_calls"):
                    tool_call = decision_response["tool_calls"][0]
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    # Parse arguments if string
                    if isinstance(arguments, str):
                        import json

                        arguments = json.loads(arguments)

                    decision_step.output = {
                        "decision": {
                            "type": "tool_call",
                            "tool": tool_name,
                            "arguments": arguments,
                        }
                    }
                    decision_step.status = "success"
                    state.add_step(decision_step)

                    # Yield STEP_START for llm_decision
                    yield (
                        decision_step,
                        self._event(AgentEventType.STEP_START, decision_step.to_dict()),
                    )

                    # Yield TOOL_CALL with step_id (belongs to llm_decision)
                    yield (
                        decision_step,
                        self._event(
                            AgentEventType.TOOL_CALL,
                            {
                                "tool": tool_name,
                                "arguments": arguments,
                                "step_id": decision_step.id,
                                "step_index": decision_step.step_index,
                            },
                        ),
                    )

                    # Yield STEP_END for llm_decision
                    yield (
                        decision_step,
                        self._event(
                            AgentEventType.STEP_END,
                            {
                                "step_index": decision_step.step_index,
                                "status": decision_step.status,
                                "output": decision_step.output,
                                "latency_ms": decision_step.latency_ms,
                            },
                        ),
                    )

                    # Add decision to messages
                    messages.append(
                        {
                            "role": "assistant",
                            "content": decision_response.get("content", ""),
                            "tool_calls": [tool_call],
                        }
                    )

                    # =================================================================
                    # Step 3a: Execute Tool (tool)
                    # =================================================================
                    tool_step = Step(
                        type=StepType.TOOL,
                        name=tool_name,
                        input={"arguments": arguments},
                        role="tool",
                    )
                    tool_start = time.time()

                    tool_result = await self._execute_tool_call(tool_name, arguments)

                    tool_step.output = tool_result
                    tool_step.status = (
                        "success" if "error" not in tool_result else "error"
                    )
                    tool_step.latency_ms = int((time.time() - tool_start) * 1000)
                    state.add_step(tool_step)
                    state.tool_results[tool_name] = tool_result

                    # Yield STEP_START for tool
                    yield (
                        tool_step,
                        self._event(AgentEventType.STEP_START, tool_step.to_dict()),
                    )

                    # Yield TOOL_RESULT
                    yield (
                        tool_step,
                        self._event(
                            AgentEventType.TOOL_RESULT,
                            {
                                "tool": tool_name,
                                "result": tool_result,
                                "step_id": tool_step.id,
                                "step_index": tool_step.step_index,
                            },
                        ),
                    )

                    # Yield STEP_END for tool
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

                    # Add tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result),
                        }
                    )

                    # =================================================================
                    # Step 3b: LLM Observe (llm_observation)
                    # =================================================================
                    if tool_step.status == "success":
                        observation_step = Step(
                            type=StepType.LLM_OBSERVATION,
                            name=self.llm.provider_name,
                            input={"tool_result": tool_result},
                        )
                        observation_start = time.time()

                        try:
                            # Generate observation based on tool result
                            observation_text = (
                                f"Observation: I used {tool_name} and got {tool_result}"
                            )

                            observation_step.latency_ms = int(
                                (time.time() - observation_start) * 1000
                            )
                            observation_step.output = {"observation": observation_text}
                            observation_step.status = "success"
                            state.add_step(observation_step)

                        except Exception as e:
                            logger.error(f"LLM observation error: {e}")
                            observation_step.status = "error"
                            observation_step.error = str(e)
                            observation_step.latency_ms = int(
                                (time.time() - observation_start) * 1000
                            )
                            state.add_step(observation_step)

                        # Yield STEP_START for llm_observation
                        yield (
                            observation_step,
                            self._event(
                                AgentEventType.STEP_START, observation_step.to_dict()
                            ),
                        )

                        # Yield OBSERVATION
                        yield (
                            observation_step,
                            self._event(
                                AgentEventType.OBSERVATION,
                                {"observation": observation_text},
                            ),
                        )

                        # Yield STEP_END for llm_observation
                        yield (
                            observation_step,
                            self._event(
                                AgentEventType.STEP_END,
                                {
                                    "step_index": observation_step.step_index,
                                    "status": observation_step.status,
                                    "output": observation_step.output,
                                    "latency_ms": observation_step.latency_ms,
                                },
                            ),
                        )

                    # Loop back for next iteration
                    loop_count += 1
                    continue

                else:
                    # =================================================================
                    # No tool call - final response (llm_response)
                    # =================================================================
                    decision_step.type = StepType.LLM_RESPONSE
                    decision_step.output = {
                        "content": decision_response.get("content", "")
                    }
                    decision_step.status = "success"
                    state.add_step(decision_step)

                    # Set state output before yielding events
                    state.output = decision_response.get("content", "")
                    state.finished = True

                    # Yield STEP_START for llm_response
                    yield (
                        decision_step,
                        self._event(AgentEventType.STEP_START, decision_step.to_dict()),
                    )

                    # Yield CONTENT
                    yield (
                        decision_step,
                        self._event(
                            AgentEventType.CONTENT,
                            {"content": decision_response.get("content", "")},
                        ),
                    )

                    # Yield STEP_END
                    yield (
                        decision_step,
                        self._event(
                            AgentEventType.STEP_END,
                            {
                                "step_index": decision_step.step_index,
                                "status": decision_step.status,
                                "output": decision_step.output,
                                "latency_ms": decision_step.latency_ms,
                            },
                        ),
                    )

                    # CRITICAL: Yield run_end with output included
                    yield (
                        None,
                        self._event(
                            AgentEventType.RUN_END,
                            {"output": state.output, "summary": state.summary},
                        ),
                    )
                    return

            except Exception as e:
                logger.error(f"LLM decision error: {e}")
                decision_step.status = "error"
                decision_step.error = str(e)
                decision_step.latency_ms = int((time.time() - decision_start) * 1000)
                state.add_step(decision_step)
                yield (
                    decision_step,
                    self._event(AgentEventType.ERROR, {"error": str(e)}),
                )
                yield (
                    None,
                    self._event(
                        AgentEventType.RUN_END,
                        {"output": state.output, "summary": state.summary},
                    ),
                )
                return

        # Max loop reached without final response
        state.output = "Max iterations reached without final response."
        state.finished = True
        yield (
            None,
            self._event(
                AgentEventType.RUN_END,
                {"output": state.output, "summary": state.summary},
            ),
        )

    def _get_thought_prompt(self) -> str:
        """Get the system prompt for the thought step."""
        return """You are a helpful AI assistant. Think through the problem step by step.

Your response should be in this format:
Thought: [your reasoning about what the user is asking and how to approach it]

Be concise but thorough in your thinking."""
