from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import ValidationError

from app.common.exceptions import NotFoundException
from app.modules.agent import router as agent_router_module
from app.modules.agent.agent_factory import create_agent
from app.modules.agent.enums import AgentTypeMode
from app.modules.agent.schema import (
    AgentConfigCreate,
    AgentConfigToolUpdate,
    AgentRunRequest,
    AgentSessionCreate,
)
from app.modules.agent.service import AgentService
from app.modules.agent.tools.base import Tool
from app.services.agent.core import (
    AgentEvent,
    AgentEventType,
    AgentState,
    Step,
    StepType,
)
from app.services.agent.simple_agent import SimpleAgent
from app.services.mcp.exceptions import MCPConnectionError
from app.services.mcp.session import create_session


class _AlwaysToolLLM:
    provider_name = "always-tool"

    async def achat(self, messages, **kwargs):
        return {
            "content": "using tool",
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {
                        "name": "echo",
                        "arguments": {"value": "x"},
                    },
                }
            ],
        }


class _EchoTool(Tool):
    name = "echo"
    description = "echo"
    input_schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }

    async def run(self, input: dict) -> dict:
        return {"value": input["value"]}


class _FakeRunAgent:
    async def run(self, state: AgentState) -> AgentState:
        state.output = "done"
        state.finished = True
        return state


class _DummyLLM:
    provider_name = "dummy"


class _FakeResumeAgent:
    async def stream_run(self, state: AgentState):
        step = Step(type=StepType.TOOL, name="calculator", input={"arguments": {"x": 1}})
        state.add_step(step)
        yield step, AgentEvent(AgentEventType.STEP_START, step.to_dict())
        yield step, AgentEvent(
            AgentEventType.STEP_END,
            {
                "step_index": step.step_index,
                "status": "success",
                "output": {"result": 1},
                "latency_ms": 1,
            },
        )
        state.output = "done"
        state.finished = True
        yield None, AgentEvent(AgentEventType.RUN_END, {"output": "done"})


@pytest.mark.asyncio
async def test_update_config_tool_handler_passes_config_and_user_context():
    service = AsyncMock()
    current_user = SimpleNamespace(id=7)
    data = AgentConfigToolUpdate(tool_config={"k": "v"}, enabled=True)

    await agent_router_module.update_config_tool(
        "cfg-1", 11, data, current_user, service
    )

    service.update_config_tool.assert_awaited_once_with(
        config_id="cfg-1",
        user_id=7,
        tool_id=11,
        tool_config={"k": "v"},
        enabled=True,
    )


@pytest.mark.asyncio
async def test_delete_config_tool_handler_passes_config_and_user_context():
    service = AsyncMock()
    service.delete_config_tool.return_value = True
    current_user = SimpleNamespace(id=7)

    await agent_router_module.delete_config_tool("cfg-1", 11, current_user, service)

    service.delete_config_tool.assert_awaited_once_with(
        config_id="cfg-1",
        user_id=7,
        tool_id=11,
    )


@pytest.mark.asyncio
async def test_unlink_handlers_pass_config_and_user_context():
    service = AsyncMock()
    service.delete_config_mcp_server.return_value = True
    service.delete_config_kb.return_value = True
    current_user = SimpleNamespace(id=9)

    await agent_router_module.unlink_mcp_server("cfg-2", 21, current_user, service)
    await agent_router_module.unlink_kb("cfg-2", 31, current_user, service)

    service.delete_config_mcp_server.assert_awaited_once_with(
        config_id="cfg-2",
        user_id=9,
        link_id=21,
    )
    service.delete_config_kb.assert_awaited_once_with(
        config_id="cfg-2",
        user_id=9,
        link_id=31,
    )


@pytest.mark.asyncio
async def test_update_session_config_rejects_foreign_or_missing_config():
    repo = AsyncMock()
    repo.get_session.return_value = SimpleNamespace(id="sess-1", user_id=1)
    repo.get_config.return_value = None
    service = AgentService(repo, AsyncMock())

    with pytest.raises(NotFoundException):
        await service.update_session_config("sess-1", 1, "cfg-missing")

    repo.update_session_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_skips_followup_events_for_already_completed_step():
    repo = AsyncMock()
    repo.get_run.return_value = SimpleNamespace(
        id="run-1",
        session_id="sess-1",
        config_snapshot=None,
    )
    repo.get_session.return_value = SimpleNamespace(
        id="sess-1",
        user_id=1,
        summary=None,
    )
    repo.get_steps.return_value = [
        SimpleNamespace(
            status="success",
            step_index=0,
            type="tool",
            name="calculator",
            output={"result": 1},
        )
    ]
    repo.get_messages.return_value = []
    repo.create_run.return_value = SimpleNamespace(id="run-2")
    repo.get_step_by_idempotency_key.return_value = SimpleNamespace(status="success")
    service = AgentService(repo, AsyncMock())
    service._get_llm_for_session = AsyncMock(return_value=SimpleNamespace())
    service._generate_summary = AsyncMock(return_value=None)

    with (
        patch("app.modules.agent.service.ToolBuilder.build", new=AsyncMock(return_value=([], []))),
        patch("app.modules.agent.service.create_agent", return_value=_FakeResumeAgent()),
    ):
        response = await service.resume_agent(
            "run-1",
            1,
            AgentRunRequest(input="resume", stream=True),
        )

        async for _ in response.body_iterator:
            pass

    repo.update_step.assert_not_awaited()
    repo.create_step.assert_not_awaited()


@pytest.mark.asyncio
async def test_simple_agent_run_honors_max_loop_on_repeated_tool_calls():
    agent = SimpleAgent(
        llm=_AlwaysToolLLM(),
        tools=[_EchoTool()],
        max_loop=2,
    )
    state = AgentState(session_id="sess-1", user_input="loop")

    result = await agent.run(state)

    assert len(result.steps) == 4


def test_agent_config_create_rejects_unknown_agent_type():
    with pytest.raises(ValidationError):
        AgentConfigCreate(name="test-agent", agent_type="invalid")


def test_create_agent_rejects_unknown_agent_type():
    with pytest.raises(ValueError, match="Unsupported agent_type"):
        create_agent(
            agent_type="invalid",
            tools=[],
            llm=_DummyLLM(),
            run_id=None,
        )


def test_create_agent_accepts_enum_value():
    agent = create_agent(
        agent_type=AgentTypeMode.SIMPLE,
        tools=[],
        llm=_DummyLLM(),
        run_id=None,
    )

    assert isinstance(agent, SimpleAgent)


def test_agent_session_create_requires_config_id():
    with pytest.raises(ValidationError):
        AgentSessionCreate()


@pytest.mark.asyncio
async def test_create_session_defaults_title_and_binds_config():
    repo = AsyncMock()
    repo.get_config.return_value = SimpleNamespace(
        id="cfg-1",
        user_id=1,
        name="cfg",
        description=None,
        llm_model_id=None,
        agent_type=AgentTypeMode.SIMPLE,
        max_loop=5,
        system_prompt=None,
        enabled=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    repo.create_session.return_value = SimpleNamespace(
        id="sess-1",
        user_id=1,
        config_id="cfg-1",
        title="默认会话",
        summary=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    service = AgentService(repo, AsyncMock())

    response = await service.create_session(
        1,
        AgentSessionCreate(config_id="cfg-1"),
    )

    repo.create_session.assert_awaited_once_with(
        user_id=1,
        config_id="cfg-1",
        title="默认会话",
    )
    assert response.config_id == "cfg-1"
    assert response.title == "默认会话"


@pytest.mark.asyncio
async def test_run_agent_updates_default_session_title_from_first_message():
    repo = AsyncMock()
    repo.get_session.return_value = SimpleNamespace(
        id="sess-1",
        user_id=1,
        config_id=None,
        title="默认会话",
        summary=None,
    )
    repo.get_messages.return_value = []
    service = AgentService(repo, AsyncMock())
    service._get_llm_for_session = AsyncMock(return_value=SimpleNamespace())
    service._generate_summary = AsyncMock(return_value=None)

    with (
        patch("app.modules.agent.service.ToolBuilder.build", new=AsyncMock(return_value=([], []))),
        patch("app.modules.agent.service.create_agent", return_value=_FakeRunAgent()),
    ):
        await service.run_agent(
            "sess-1",
            1,
            AgentRunRequest(input="请帮我调研 MCP 架构设计", stream=False),
        )

    repo.update_session_title.assert_awaited_once()
    assert repo.update_session_title.await_args.args[0] == "sess-1"
    assert repo.update_session_title.await_args.args[1].startswith("请帮我调研 MCP 架构设计")


@pytest.mark.asyncio
async def test_run_agent_uses_request_mcp_server_ids():
    repo = AsyncMock()
    repo.get_session.return_value = SimpleNamespace(
        id="sess-1",
        user_id=1,
        config_id=None,
        summary=None,
    )
    repo.get_messages.return_value = []
    repo.get_mcp_servers.return_value = [
        SimpleNamespace(
            id="mcp-1",
            name="GitHub MCP",
            transport="streamable_http",
            url="https://example.com/mcp",
            headers=None,
            command=None,
            args=None,
            env=None,
            cwd=None,
            enabled=True,
        )
    ]
    service = AgentService(repo, AsyncMock())
    service._get_llm_for_session = AsyncMock(return_value=SimpleNamespace())

    captured_configs = []

    async def _capture_build(config):
        captured_configs.append(config)
        return [], []

    with (
        patch("app.modules.agent.service.ToolBuilder.build", new=AsyncMock(side_effect=_capture_build)),
        patch("app.modules.agent.service.create_agent", return_value=_FakeRunAgent()),
    ):
        await service.run_agent(
            "sess-1",
            1,
            AgentRunRequest(input="hello", stream=False, mcp_server_ids=["mcp-1"]),
        )

    assert captured_configs
    assert captured_configs[0] is not None
    assert [server.mcp_server_id for server in captured_configs[0].mcp_servers] == [
        "mcp-1"
    ]


@pytest.mark.asyncio
async def test_get_config_handler_uses_detail_fetch():
    service = AsyncMock()
    service.get_config_detail.return_value = {"id": "cfg-1", "tools": []}
    current_user = SimpleNamespace(id=7)

    response = await agent_router_module.get_config("cfg-1", current_user, service)

    service.get_config_detail.assert_awaited_once_with("cfg-1", 7)
    assert response.data == {"id": "cfg-1", "tools": []}


@pytest.mark.asyncio
async def test_get_config_detail_returns_base_and_related_resources():
    repo = AsyncMock()
    repo.get_config_detail.return_value = SimpleNamespace(
        id="cfg-1",
        user_id=1,
        name="Research Agent",
        description="desc",
        llm_model_id="llm-1",
        agent_type="simple",
        max_loop=5,
        system_prompt="prompt",
        enabled=True,
        created_at=SimpleNamespace(isoformat=lambda: "2026-04-09T00:00:00Z"),
        updated_at=SimpleNamespace(isoformat=lambda: "2026-04-09T01:00:00Z"),
        tools=[
            SimpleNamespace(
                id=1,
                config_id="cfg-1",
                tool_name="calculator",
                tool_config={},
                enabled=True,
            )
        ],
        mcp_links=[
            SimpleNamespace(
                id=2,
                config_id="cfg-1",
                mcp_server_id="mcp-1",
            )
        ],
        kb_links=[
            SimpleNamespace(
                id=3,
                config_id="cfg-1",
                kb_id="kb-1",
                kb_config={"top_k": 5},
            )
        ],
    )
    service = AgentService(repo, AsyncMock())

    result = await service.get_config_detail("cfg-1", 1)

    assert result == {
        "id": "cfg-1",
        "user_id": 1,
        "name": "Research Agent",
        "description": "desc",
        "llm_model_id": "llm-1",
        "agent_type": "simple",
        "max_loop": 5,
        "system_prompt": "prompt",
        "enabled": True,
        "created_at": "2026-04-09T00:00:00Z",
        "updated_at": "2026-04-09T01:00:00Z",
        "tools": [
            {
                "id": 1,
                "config_id": "cfg-1",
                "tool_name": "calculator",
                "tool_config": {},
                "enabled": True,
            }
        ],
        "mcp_servers": [
            {
                "id": 2,
                "config_id": "cfg-1",
                "mcp_server_id": "mcp-1",
            }
        ],
        "kbs": [
            {
                "id": 3,
                "config_id": "cfg-1",
                "kb_id": "kb-1",
                "kb_config": {"top_k": 5},
            }
        ],
    }


@pytest.mark.asyncio
async def test_get_builtin_tools_includes_rag_retrieval():
    service = AgentService(AsyncMock(), AsyncMock())

    tools = await service.get_builtin_tools()

    assert "rag_retrieval" in {tool["name"] for tool in tools}


@pytest.mark.asyncio
async def test_create_session_unwraps_streamable_http_exception_group():
    request = httpx.Request("POST", "https://example.com/mcp")
    response = httpx.Response(
        401,
        request=request,
        text='{"error":"unauthorized"}',
    )

    @asynccontextmanager
    async def _fake_streamable_http_client(*_args, **_kwargs):
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [
                httpx.HTTPStatusError(
                    "Client error '401 Unauthorized' for url 'https://example.com/mcp'",
                    request=request,
                    response=response,
                )
            ],
        )
        yield

    with patch(
        "app.services.mcp.session.streamable_http_client",
        _fake_streamable_http_client,
    ):
        with pytest.raises(MCPConnectionError, match="401 Unauthorized"):
            async with create_session(
                transport="streamable_http",
                url="https://example.com/mcp",
            ):
                pass


@pytest.mark.asyncio
async def test_test_mcp_server_surfaces_unwrapped_connection_error():
    repo = AsyncMock()
    repo.get_mcp_server.return_value = SimpleNamespace(
        id="mcp-1",
        user_id=1,
        name="tavily-mcp",
        transport="streamable_http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer token"},
        command=None,
        args=None,
        env=None,
        cwd=None,
        enabled=True,
    )
    service = AgentService(repo, AsyncMock())

    @asynccontextmanager
    async def _failing_session(*_args, **_kwargs):
        raise MCPConnectionError("HTTP 401 Unauthorized: unauthorized")
        yield

    with patch("app.services.mcp.session.create_session", _failing_session):
        result = await service.test_mcp_server("mcp-1", 1)

    assert result == {
        "success": False,
        "message": "Connection failed: HTTP 401 Unauthorized: unauthorized",
        "tools_count": 0,
    }


@pytest.mark.asyncio
async def test_test_mcp_server_diagnoses_session_terminated_for_streamable_http():
    repo = AsyncMock()
    repo.get_mcp_server.return_value = SimpleNamespace(
        id="mcp-2",
        user_id=1,
        name="tavily-mcp",
        transport="streamable_http",
        url="https://api.tavily.com/mcp",
        headers={"Authorization": "Bearer token"},
        command=None,
        args=None,
        env=None,
        cwd=None,
        enabled=True,
    )
    service = AgentService(repo, AsyncMock())

    @asynccontextmanager
    async def _terminated_session(*_args, **_kwargs):
        raise MCPConnectionError("Session terminated")
        yield

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.headers = kwargs.get("headers")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            request = httpx.Request("POST", url, headers=self.headers)
            return httpx.Response(
                404,
                request=request,
                text='{"detail":"Not Found"}',
            )

    with (
        patch("app.services.mcp.session.create_session", _terminated_session),
        patch("app.modules.agent.service.httpx.AsyncClient", _FakeAsyncClient),
    ):
        result = await service.test_mcp_server("mcp-2", 1)

    assert result == {
        "success": False,
        "message": (
            "Connection failed: HTTP 404 Not Found while connecting to "
            "https://api.tavily.com/mcp. The MCP endpoint may be incorrect."
        ),
        "tools_count": 0,
    }
