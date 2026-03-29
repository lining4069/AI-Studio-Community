"""
ReAct Agent Implementation.

Implements a ReAct (Reasoning + Acting) agent loop with tool calling support.
"""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from app.modules.agent.tools.base import (
    ToolRegistry,
    ToolResult,
)
from app.modules.agent.tools.knowledge_base import create_kb_tools
from app.modules.agent.tools.mcp import create_mcp_tools
from app.modules.agent.tools.websearch import create_websearch_tool_from_config


@dataclass
class AgentMessage:
    """Message in agent conversation"""

    role: str  # system, user, assistant, tool
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class AgentState:
    """State for the agent loop"""

    messages: list[AgentMessage] = field(default_factory=list)
    step: int = 0


@dataclass
class AgentConfig:
    """Configuration for the agent"""

    name: str
    system_prompt: str
    llm_model_id: str
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_top_p: float | None = None
    llm_timeout: int = 120
    max_steps: int = 20
    return_raw_response: bool = False


class ReactAgent:
    """
    ReAct Agent with tool calling capabilities.

    Implements a loop of:
    1. Think (LLM generates reasoning)
    2. Act (LLM calls tools if needed)
    3. Observe (Get tool results)
    4. Repeat until completion
    """

    def __init__(
        self,
        config: AgentConfig,
        tool_registry: ToolRegistry,
        llm_provider,
    ):
        """
        Initialize ReAct Agent.

        Args:
            config: Agent configuration
            tool_registry: Registry of available tools
            llm_provider: LLM provider instance for chat completions
        """
        self.config = config
        self.tool_registry = tool_registry
        self.llm_provider = llm_provider
        self.max_steps = config.max_steps

    def _build_system_message(self) -> str:
        """Build the system prompt with tool definitions"""
        tools = self.tool_registry.get_definitions()

        # Build tools section
        tools_description = []
        for tool in tools:
            params = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])

            params_str = []
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "string")
                param_desc = param_info.get("description", "")
                is_required = param_name in required
                required_mark = "必需" if is_required else "可选"
                params_str.append(
                    f"  - {param_name} ({param_type}, {required_mark}): {param_desc}"
                )

            params_block = "\n".join(params_str) if params_str else "  (无参数)"
            tools_description.append(
                f"## {tool.name}\n描述: {tool.description}\n参数:\n{params_block}"
            )

        tools_section = (
            "\n\n".join(tools_description) if tools_description else "（无可用工具）"
        )

        system_prompt = f"""{self.config.system_prompt}

## 可用工具

{tools_section}

## 工具使用规则

1. 当你需要使用工具时，在回复中包含 tool_calls
2. 每个 tool_call 需要包含:
   - id: 唯一标识符，格式为 "call_{{uuid}}"
   - function: 包含 name 和 arguments
3. 等待工具执行结果后，继续对话
4. 如果信息足够回答，直接给出答案

## 当前时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        return system_prompt

    async def run(
        self,
        messages: list[dict[str, Any]],
        stream: bool = True,
    ) -> AsyncGenerator[tuple[str, ToolResult | None], None]:
        """
        Run the agent loop.

        Args:
            messages: Conversation messages
            stream: Whether to stream the response

        Yields:
            Tuples of (text_delta, tool_result)
            - text_delta: Text chunk from LLM
            - tool_result: Tool execution result (None for text)
        """
        # Build initial messages
        system_msg = self._build_system_message()
        formatted_messages = [{"role": "system", "content": system_msg}]

        # Add conversation history
        for msg in messages:
            formatted_messages.append(
                {
                    "role": msg["role"],
                    "content": msg.get("content", ""),
                }
            )

        # Get tools for this turn
        tools = self.tool_registry.get_openai_tools()

        step = 0
        while step < self.max_steps:
            step += 1
            logger.debug(f"Agent step {step}/{self.max_steps}")

            tool_calls = None
            assistant_content = ""

            # Call LLM with tools
            try:
                response = await self.llm_provider.achat(
                    messages=formatted_messages,
                    tools=tools if tools else None,
                    temperature=self.config.llm_temperature,
                    max_tokens=self.config.llm_max_tokens,
                    top_p=self.config.llm_top_p,
                )
            except Exception as e:
                yield f"LLM调用失败: {str(e)}", None
                return

            # Process response
            if isinstance(response, dict):
                # Non-streaming response
                assistant_content = response.get("content", "")
                message_content = assistant_content

                # Check for tool calls
                tool_calls = response.get("tool_calls", [])
            elif isinstance(response, str):
                # Simple string response
                assistant_content = response
                message_content = response
            else:
                assistant_content = str(response)
                message_content = assistant_content

            # Add assistant message
            if message_content:
                formatted_messages.append(
                    {
                        "role": "assistant",
                        "content": message_content,
                    }
                )
                yield message_content, None

            # If no tool calls, we're done
            if not tool_calls:
                break

            # Execute tool calls
            for tool_call in tool_calls:
                call_id = tool_call.get("id", f"call_{step}")
                function = tool_call.get("function", {})
                tool_name = function.get("name", "")
                arguments = function.get("arguments", {})

                # Parse arguments if string
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                logger.info(f"Executing tool: {tool_name} with args: {arguments}")

                # Execute tool
                tool_result = await self.tool_registry.execute(tool_name, arguments)

                # Add tool result message
                formatted_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": tool_result.content
                        if tool_result.success
                        else f"Error: {tool_result.error}",
                    }
                )

                # Yield tool result
                yield "", tool_result

            # Check if any tool has return_direct (end conversation)
            # For now, we continue the loop

        # If max steps reached
        if step >= self.max_steps:
            yield "\n\n(达到最大步数限制)", None


async def create_agent_tools(
    kb_ids: list[str],
    mcp_ids: list[str],
    enable_websearch: bool,
    websearch_config,
    user_id: int,
    db,
) -> ToolRegistry:
    """
    Create and populate a tool registry for an agent.

    Args:
        kb_ids: Knowledge base IDs to mount
        mcp_ids: MCP server IDs to mount
        enable_websearch: Whether to enable web search
        websearch_config: WebSearchConfig instance
        user_id: User ID
        db: Database session

    Returns:
        Populated ToolRegistry
    """
    from app.modules.agent.repository import McpServerRepository

    registry = ToolRegistry()

    # Add knowledge base tools
    if kb_ids:
        kb_tools = await create_kb_tools(kb_ids, user_id, db)
        for tool in kb_tools:
            registry.register(tool)

    # Add MCP tools
    if mcp_ids:
        mcp_repo = McpServerRepository(db)
        mcp_servers = await mcp_repo.list_by_ids(mcp_ids, user_id)
        if mcp_servers:
            mcp_tools = await create_mcp_tools(mcp_servers)
            for tool in mcp_tools:
                registry.register(tool)

    # Add web search tool
    if enable_websearch and websearch_config:
        try:
            websearch_tool = create_websearch_tool_from_config(
                encrypted_api_key=websearch_config.encrypted_api_key,
                provider=websearch_config.provider,
                search_count=websearch_config.search_count,
            )
            registry.register(websearch_tool)
        except Exception as e:
            logger.warning(f"Failed to create websearch tool: {e}")

    return registry
