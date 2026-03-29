"""
Agent service for business logic.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from app.common.exceptions import NotFoundException, ValidationException
from app.modules.agent.agent import (
    AgentConfig,
    ReactAgent,
    create_agent_tools,
)
from app.modules.agent.models import (
    Agent,
    KbRetrievalMode,
    McpServer,
    WebSearchConfig,
)
from app.modules.agent.repository import (
    AgentRepository,
    AgentSessionRepository,
    McpServerRepository,
    WebSearchConfigRepository,
)
from app.modules.agent.schema import ChatRequest, ToolCallResult
from app.modules.llm_model.repository import LlmModelRepository
from app.services.factory.model_factory import create_llm


class AgentService:
    """Business logic for Agent management and chat"""

    def __init__(
        self,
        agent_repo: AgentRepository,
        session_repo: AgentSessionRepository,
        ws_config_repo: WebSearchConfigRepository,
        mcp_repo: McpServerRepository,
    ):
        self.agent_repo = agent_repo
        self.session_repo = session_repo
        self.ws_config_repo = ws_config_repo
        self.mcp_repo = mcp_repo

    # =========================================================================
    # Agent CRUD
    # =========================================================================

    async def create_agent(self, user_id: int, data) -> Agent:
        """Create a new Agent"""
        # Validate LLM model if provided
        if data.llm_model_id:
            llm_repo = LlmModelRepository(self.agent_repo.db)
            model = await llm_repo.get_by_id(data.llm_model_id, user_id)
            if not model:
                raise ValidationException(
                    f"LLM模型 '{data.llm_model_id}' 不存在或无权限"
                )

        # Validate KBs if provided
        if data.kb_ids:
            from app.modules.knowledge_base.repository import KbDocumentRepository

            kb_repo = KbDocumentRepository(self.agent_repo.db)
            for kb_id in data.kb_ids:
                kb = await kb_repo.get_by_id(kb_id, user_id)
                if not kb:
                    raise ValidationException(f"知识库 '{kb_id}' 不存在或无权限")

        # Validate WebSearch config if provided
        if data.websearch_config_id:
            ws_config = await self.ws_config_repo.get_by_id(
                data.websearch_config_id, user_id
            )
            if not ws_config:
                raise ValidationException(
                    f"网络搜索配置 '{data.websearch_config_id}' 不存在或无权限"
                )

        # Validate MCP servers if provided
        if data.mcp_ids:
            servers = await self.mcp_repo.list_by_ids(data.mcp_ids, user_id)
            if len(servers) != len(data.mcp_ids):
                raise ValidationException("部分MCP服务器不存在或无权限")

        return await self.agent_repo.create(user_id, data)

    async def get_agent(self, agent_id: str, user_id: int) -> Agent:
        """Get an Agent by ID"""
        agent = await self.agent_repo.get_by_id(agent_id, user_id)
        if not agent:
            raise NotFoundException("Agent", agent_id)
        return agent

    async def list_agents(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[Agent], int]:
        """List Agents for a user"""
        return await self.agent_repo.list_by_user(user_id, page, page_size)

    async def update_agent(self, agent_id: str, user_id: int, data) -> Agent:
        """Update an Agent"""
        agent = await self.get_agent(agent_id, user_id)

        # Validate LLM model if changing
        if data.llm_model_id and data.llm_model_id != agent.llm_model_id:
            llm_repo = LlmModelRepository(self.agent_repo.db)
            model = await llm_repo.get_by_id(data.llm_model_id, user_id)
            if not model:
                raise ValidationException(
                    f"LLM模型 '{data.llm_model_id}' 不存在或无权限"
                )

        return await self.agent_repo.update(agent, data)

    async def delete_agent(self, agent_id: str, user_id: int) -> None:
        """Delete an Agent and its sessions"""
        agent = await self.get_agent(agent_id, user_id)
        # Delete sessions first
        await self.session_repo.delete_by_agent(agent_id)
        # Delete agent
        await self.agent_repo.delete(agent)

    # =========================================================================
    # WebSearch Config CRUD
    # =========================================================================

    async def create_websearch_config(self, user_id: int, data) -> WebSearchConfig:
        """Create a new WebSearchConfig"""
        return await self.ws_config_repo.create(user_id, data)

    async def get_websearch_config(
        self, config_id: str, user_id: int
    ) -> WebSearchConfig:
        """Get a WebSearchConfig by ID"""
        config = await self.ws_config_repo.get_by_id(config_id, user_id)
        if not config:
            raise NotFoundException("WebSearchConfig", config_id)
        return config

    async def list_websearch_configs(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[WebSearchConfig], int]:
        """List WebSearchConfigs for a user"""
        return await self.ws_config_repo.list_by_user(user_id, page, page_size)

    async def update_websearch_config(
        self, config_id: str, user_id: int, data
    ) -> WebSearchConfig:
        """Update a WebSearchConfig"""
        config = await self.get_websearch_config(config_id, user_id)
        return await self.ws_config_repo.update(config, data)

    async def delete_websearch_config(self, config_id: str, user_id: int) -> None:
        """Delete a WebSearchConfig"""
        config = await self.get_websearch_config(config_id, user_id)
        await self.ws_config_repo.delete(config)

    # =========================================================================
    # MCP Server CRUD
    # =========================================================================

    async def create_mcp_server(self, user_id: int, data) -> McpServer:
        """Create a new McpServer"""
        return await self.mcp_repo.create(user_id, data)

    async def get_mcp_server(self, server_id: str, user_id: int) -> McpServer:
        """Get a McpServer by ID"""
        server = await self.mcp_repo.get_by_id(server_id, user_id)
        if not server:
            raise NotFoundException("McpServer", server_id)
        return server

    async def list_mcp_servers(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[McpServer], int]:
        """List McpServers for a user"""
        return await self.mcp_repo.list_by_user(user_id, page, page_size)

    async def update_mcp_server(self, server_id: str, user_id: int, data) -> McpServer:
        """Update a McpServer"""
        server = await self.get_mcp_server(server_id, user_id)
        return await self.mcp_repo.update(server, data)

    async def delete_mcp_server(self, server_id: str, user_id: int) -> None:
        """Delete a McpServer"""
        server = await self.get_mcp_server(server_id, user_id)
        await self.mcp_repo.delete(server)

    # =========================================================================
    # Chat
    # =========================================================================

    async def chat(
        self,
        user_id: int,
        request: ChatRequest,
    ) -> AsyncGenerator[tuple[str, ToolCallResult | None], None]:
        """
        Chat with an Agent.

        Args:
            user_id: User ID
            request: Chat request

        Yields:
            Tuples of (text_chunk, tool_result)
        """
        # Get agent
        agent = await self.get_agent(request.agent_id, user_id)

        if not agent.llm_model_id:
            yield "Agent未配置LLM模型，请先配置", None
            return

        # Get LLM model
        llm_repo = LlmModelRepository(self.agent_repo.db)
        llm_model = await llm_repo.get_by_id(agent.llm_model_id, user_id)
        if not llm_model:
            yield "LLM模型不存在", None
            return

        # Create LLM provider with agent-specific parameters
        llm_provider = create_llm(llm_model)

        # Override with agent-specific parameters
        # Note: The create_llm uses model's default temperature
        # For agent-isolated params, we need to pass them to the provider
        if hasattr(llm_provider, "temperature"):
            llm_provider.temperature = agent.llm_temperature
        if hasattr(llm_provider, "max_tokens"):
            llm_provider.max_tokens = agent.llm_max_tokens

        # Get or create session
        session_id = request.session_id or uuid.uuid4().hex
        session = await self.session_repo.get_or_create(
            user_id=user_id,
            agent_id=agent.id,
            session_id=session_id,
        )

        # Prepare messages and save user messages to session
        formatted_messages = []
        for msg in request.messages:
            msg_dict = {
                "role": msg.role,
                "content": msg.content,
            }
            formatted_messages.append(msg_dict)
            # Save user and assistant messages to session
            if msg.role in ("user", "assistant"):
                await self.session_repo.append_message(session, msg_dict)

        # Build system prompt
        system_prompt = agent.system_prompt or self._get_default_system_prompt(agent)

        # Get websearch config if enabled
        websearch_config = None
        if agent.enable_websearch and agent.websearch_config_id:
            websearch_config = await self.ws_config_repo.get_by_id(
                agent.websearch_config_id, user_id
            )

        # Create tool registry
        tool_registry = await create_agent_tools(
            kb_ids=agent.kb_ids,
            mcp_ids=agent.mcp_ids,
            enable_websearch=agent.enable_websearch,
            websearch_config=websearch_config,
            user_id=user_id,
            db=self.agent_repo.db,
        )

        # Create agent config
        agent_config = AgentConfig(
            name=agent.name,
            system_prompt=system_prompt,
            llm_model_id=agent.llm_model_id,
            llm_temperature=agent.llm_temperature,
            llm_max_tokens=agent.llm_max_tokens,
            llm_top_p=agent.llm_top_p,
            llm_timeout=agent.llm_timeout,
            max_steps=agent.max_steps,
            return_raw_response=agent.return_raw_response,
        )

        # Create ReAct agent
        react_agent = ReactAgent(
            config=agent_config,
            tool_registry=tool_registry,
            llm_provider=llm_provider,
        )

        # Collect tool results for response
        all_tool_results = []
        full_response = []

        # Run agent
        async for text_delta, tool_result in react_agent.run(
            messages=formatted_messages,
            stream=request.stream,
        ):
            if text_delta:
                full_response.append(text_delta)
                yield text_delta, None

            if tool_result:
                tool_call_result = ToolCallResult(
                    tool_call_id=uuid.uuid4().hex,
                    tool_name=tool_result.metadata.get("tool_name", "unknown"),
                    content=tool_result.content,
                    error=tool_result.error,
                )
                all_tool_results.append(tool_call_result)
                yield "", tool_call_result

        # Save session
        assistant_message = {"role": "assistant", "content": "".join(full_response)}
        await self.session_repo.append_message(session, assistant_message)

        # Save tool results as special messages
        for tr in all_tool_results:
            await self.session_repo.append_message(
                session,
                {
                    "role": "tool",
                    "content": tr.content,
                    "tool_name": tr.tool_name,
                    "error": tr.error,
                },
            )

    def _get_default_system_prompt(self, agent: Agent) -> str:
        """Get default system prompt based on agent configuration"""
        prompts = []

        # Base prompt
        prompts.append(f"你是一个AI助手，名称为「{agent.name}」。")
        if agent.description:
            prompts.append(f"功能描述：{agent.description}")

        # Knowledge base mode
        if agent.kb_ids:
            if agent.kb_retrieval_mode == KbRetrievalMode.FORCE.value:
                prompts.append(
                    "你具备从知识库中检索信息的能力。"
                    "当用户询问问题时，你应该主动从知识库中搜索相关信息来回答。"
                )
            else:  # INTENT mode
                prompts.append(
                    "你具备从知识库中检索信息的能力。"
                    "当用户的问题需要查找具体信息时，可以使用知识库搜索工具。"
                )

        # Web search mode
        if agent.enable_websearch:
            prompts.append("你具备网络搜索能力，可以查找最新信息和网络资源。")

        return "\n".join(prompts)

    async def get_session_messages(
        self,
        agent_id: str,
        session_id: str,
        user_id: int,
    ) -> list[dict[str, Any]]:
        """Get messages from a session"""
        session = await self.session_repo.get_by_session_id(
            session_id, user_id, agent_id
        )
        if not session:
            return []
        return session.messages
