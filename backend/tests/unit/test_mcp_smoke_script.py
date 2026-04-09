from pathlib import Path

import pytest

import tests.unit.test_mcp_smoke as test_mcp_smoke


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict:
        return self._payload


class FakeHttpClient:
    def __init__(self):
        self.calls: list[tuple[str, str, dict | None]] = []
        self._responses: list[FakeResponse] = [
            FakeResponse(201, {"data": {"id": "cfg-1"}}),
            FakeResponse(201, {"data": {"id": 1, "tool_name": "calculator"}}),
            FakeResponse(201, {"data": {"id": 2, "tool_name": "datetime"}}),
            FakeResponse(201, {"data": {"id": "mcp-1"}}),
            FakeResponse(200, {"data": {"success": True, "tools_count": 2}}),
            FakeResponse(201, {"data": {"id": 3}}),
            FakeResponse(
                200,
                {
                    "data": {
                        "tools": [
                            {"name": "calculator"},
                            {"name": "datetime"},
                            {"name": "echo"},
                            {"name": "add"},
                        ],
                        "warnings": [],
                    }
                },
            ),
            FakeResponse(
                200,
                {
                    "data": {
                        "tools": [
                            {"name": "calculator"},
                            {"name": "datetime"},
                            {"name": "rag_retrieval"},
                        ]
                    }
                },
            ),
            FakeResponse(201, {"data": {"id": "sess-1"}}),
            FakeResponse(204, {"data": None}),
        ]

    def request(self, method: str, url: str, json: dict | None = None) -> FakeResponse:
        self.calls.append((method, url, json))
        if not self._responses:
            raise AssertionError(f"unexpected call: {method} {url}")
        return self._responses.pop(0)


def test_check_response_validates_status_and_returns_data():
    response = FakeResponse(201, {"data": {"id": "cfg-1"}})

    data = test_mcp_smoke.check_response(response, expected_status=201)

    assert data == {"id": "cfg-1"}


def test_check_response_rejects_unexpected_status():
    response = FakeResponse(200, {"data": {"id": "cfg-1"}})

    with pytest.raises(test_mcp_smoke.SmokeTestError):
        test_mcp_smoke.check_response(response, expected_status=201)


def test_create_echo_mcp_server_writes_fastmcp_entrypoint(tmp_path: Path):
    server_path = test_mcp_smoke.create_echo_mcp_server(tmp_path)

    content = server_path.read_text()
    assert "from mcp.server.fastmcp import FastMCP" in content
    assert 'mcp.run(transport="stdio")' in content


def test_run_smoke_test_binds_config_via_patch_after_session_creation(tmp_path: Path):
    http = FakeHttpClient()
    runner = test_mcp_smoke.SmokeRunner(
        http=http,
        base_url="http://127.0.0.1:8000",
        token="token",
        workspace=tmp_path,
        out=lambda _: None,
    )

    result = runner.run_setup_only()

    assert result.config_id == "cfg-1"
    assert result.mcp_server_id == "mcp-1"
    assert result.session_id == "sess-1"
    assert http.calls[8][0] == "POST"
    assert http.calls[8][1].endswith("/v1/agent/sessions")
    assert http.calls[8][2] == {"title": result.session_title}
    assert http.calls[9][0] == "PATCH"
    assert http.calls[9][1].endswith("/v1/agent/sessions/sess-1/config")
    assert http.calls[9][2] == {"config_id": "cfg-1"}


def test_mock_stdio_server_fixture_exposes_echo_and_add_tools():
    server_path = Path("tests/fixtures/mcp/mock_stdio_server.py")

    assert server_path.exists()

    content = server_path.read_text()
    assert "from mcp.server.fastmcp import FastMCP" in content
    assert 'mcp = FastMCP("mock-stdio-mcp")' in content
    assert "def echo(text: str) -> str:" in content
    assert "def add(a: int, b: int) -> int:" in content
    assert 'mcp.run(transport="stdio")' in content
