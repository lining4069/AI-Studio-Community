#!/usr/bin/env python3
"""
MCP Phase 5 smoke test runner.

This script validates the backend-facing MCP flow:
1. Create AgentConfig
2. Add builtin tools
3. Create stdio MCP server
4. Test MCP connectivity
5. Link MCP server to config
6. Verify resolved tools and builtin tools
7. Create session, then bind config via PATCH
8. Optionally run a builtin-tool request and a best-effort MCP-tool request

Usage:
    python test_mcp_smoke.py <base_url> <token>
"""

from __future__ import annotations

import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


class SmokeTestError(Exception):
    """Raised when a smoke-test step fails."""


def check_response(resp: requests.Response, expected_status: int = 200) -> dict:
    """Validate APIResponse shape and return its `data` payload."""
    if resp.status_code != expected_status:
        raise SmokeTestError(
            f"Expected HTTP {expected_status}, got {resp.status_code}: {resp.text}"
        )
    if expected_status == 204:
        return {}

    payload = resp.json()
    if "data" not in payload:
        raise SmokeTestError(f"Malformed response: missing `data` field: {payload}")
    return payload["data"]


def create_echo_mcp_server(workspace: Path) -> Path:
    """Create a minimal FastMCP stdio server script."""
    workspace.mkdir(parents=True, exist_ok=True)
    server_path = workspace / "echo_mcp_server.py"
    server_path.write_text(
        """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("echo-mcp")


@mcp.tool()
def echo(message: str) -> str:
    return f"Echo: {message}"


@mcp.tool()
def add(a: float, b: float) -> str:
    return f"Result: {a + b}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
""".strip()
        + "\n"
    )
    return server_path


@dataclass
class SetupResult:
    config_id: str
    mcp_server_id: str
    session_id: str
    session_title: str
    server_path: Path


class RequestsHttpClient:
    """Thin adapter to make smoke flow testable."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def request(
        self, method: str, url: str, json: dict[str, Any] | None = None
    ) -> requests.Response:
        return requests.request(method, url, headers=self.headers, json=json, timeout=30.0)


class SmokeRunner:
    def __init__(
        self,
        http: Any,
        base_url: str,
        token: str,
        workspace: Path,
        out=print,
    ):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.workspace = workspace
        self.out = out
        self._config_id: str | None = None
        self._mcp_server_id: str | None = None
        self._session_id: str | None = None
        self._session_title: str | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None, expected_status: int = 200
    ) -> dict:
        response = self.http.request(method, self._url(path), json=json)
        return check_response(response, expected_status=expected_status)

    def run_setup_only(self) -> SetupResult:
        suffix = int(time.time())
        config_name = f"mcp-smoke-{suffix}"
        session_title = f"mcp-smoke-session-{suffix}"

        self.out(f"[1/10] creating config: {config_name}")
        config = self._request(
            "POST",
            "/v1/agent/configs",
            json={"name": config_name, "agent_type": "simple", "max_loop": 5},
            expected_status=201,
        )
        config_id = config["id"]
        self._config_id = config_id

        self.out("[2/10] adding builtin tools")
        for tool_name in ("calculator", "datetime"):
            self._request(
                "POST",
                f"/v1/agent/configs/{config_id}/tools",
                json={"tool_name": tool_name},
                expected_status=201,
            )

        self.out("[3/10] creating stdio echo MCP server file")
        server_path = create_echo_mcp_server(self.workspace)

        self.out("[4/10] creating MCP server resource")
        mcp_server = self._request(
            "POST",
            "/v1/agent/mcp-servers",
            json={
                "name": f"echo-mcp-{suffix}",
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(server_path)],
                "enabled": True,
            },
            expected_status=201,
        )
        mcp_server_id = mcp_server["id"]
        self._mcp_server_id = mcp_server_id

        self.out("[5/10] testing MCP connectivity")
        test_result = self._request(
            "POST",
            f"/v1/agent/mcp-servers/{mcp_server_id}/test",
        )
        if not test_result.get("success"):
            raise SmokeTestError(f"MCP connectivity failed: {test_result}")
        if test_result.get("tools_count", 0) < 2:
            raise SmokeTestError(f"Unexpected MCP tool count: {test_result}")

        self.out("[6/10] linking MCP server to config")
        self._request(
            "POST",
            f"/v1/agent/configs/{config_id}/mcp-servers",
            json={"mcp_server_id": mcp_server_id},
            expected_status=201,
        )

        self.out("[7/10] verifying resolved tools")
        resolved = self._request("GET", f"/v1/agent/configs/{config_id}/resolved-tools")
        tool_names = {tool["name"] for tool in resolved.get("tools", [])}
        expected_tools = {"calculator", "datetime", "echo", "add"}
        missing = expected_tools - tool_names
        if missing:
            raise SmokeTestError(f"resolved-tools missing: {sorted(missing)}")

        self.out("[8/10] verifying builtin tools catalog")
        builtin = self._request("GET", "/v1/agent/builtin-tools")
        builtin_names = {tool["name"] for tool in builtin.get("tools", [])}
        if "rag_retrieval" not in builtin_names:
            raise SmokeTestError("builtin-tools missing rag_retrieval")

        self.out("[9/10] creating session")
        session = self._request(
            "POST",
            "/v1/agent/sessions",
            json={"title": session_title},
            expected_status=201,
        )
        session_id = session["id"]
        self._session_id = session_id
        self._session_title = session_title

        self.out("[10/10] binding config to session")
        self._request(
            "PATCH",
            f"/v1/agent/sessions/{session_id}/config",
            json={"config_id": config_id},
            expected_status=204,
        )

        return SetupResult(
            config_id=config_id,
            mcp_server_id=mcp_server_id,
            session_id=session_id,
            session_title=session_title,
            server_path=server_path,
        )

    def run_builtin_smoke(self, session_id: str) -> dict:
        self.out("[builtin] running calculator request")
        result = self._request(
            "POST",
            f"/v1/agent/sessions/{session_id}/runs",
            json={"input": "请使用 calculator 工具计算 1+2*3，并直接返回结果", "stream": False},
        )
        output = (result.get("output") or "").strip()
        if not output:
            raise SmokeTestError(f"builtin run returned empty output: {result}")
        return result

    def run_mcp_best_effort(self, session_id: str) -> dict:
        self.out("[mcp] attempting best-effort echo tool run")
        result = self._request(
            "POST",
            f"/v1/agent/sessions/{session_id}/runs",
            json={
                "input": "请仅调用 echo 工具，并传入 message='hello smoke'",
                "stream": False,
            },
        )
        return result

    def cleanup(self) -> None:
        if self._config_id:
            try:
                self.http.request(
                    "DELETE",
                    self._url(f"/v1/agent/configs/{self._config_id}"),
                    json=None,
                )
            except Exception:
                pass
        if self._mcp_server_id:
            try:
                self.http.request(
                    "DELETE",
                    self._url(f"/v1/agent/mcp-servers/{self._mcp_server_id}"),
                    json=None,
                )
            except Exception:
                pass

    def run(self) -> None:
        self.out("=" * 60)
        self.out("MCP Phase 5 smoke test")
        self.out(f"URL: {self.base_url}")
        self.out("=" * 60)

        try:
            setup = self.run_setup_only()
            builtin_result = self.run_builtin_smoke(setup.session_id)
            mcp_result = self.run_mcp_best_effort(setup.session_id)

            self.out("")
            self.out("Smoke summary")
            self.out(f"- config_id: {setup.config_id}")
            self.out(f"- mcp_server_id: {setup.mcp_server_id}")
            self.out(f"- session_id: {setup.session_id}")
            self.out(f"- builtin output: {(builtin_result.get('output') or '').strip()}")

            mcp_output = (mcp_result.get("output") or "").strip()
            if mcp_output:
                self.out(f"- best-effort MCP output: {mcp_output}")
            else:
                self.out("- best-effort MCP output: empty")

            self.out("")
            self.out("Notes:")
            self.out("- The setup path is deterministic and required.")
            self.out("- The final MCP run depends on model behavior and is best-effort.")
            self.out("- Session cleanup is not attempted because the current API has no delete-session endpoint.")
        finally:
            self.cleanup()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        sys.stderr.write("Usage: python test_mcp_smoke.py <base_url> <token>\n")
        return 1

    base_url = argv[1]
    token = argv[2]
    workspace = Path(tempfile.mkdtemp(prefix="mcp-smoke-"))
    runner = SmokeRunner(
        http=RequestsHttpClient(base_url=base_url, token=token),
        base_url=base_url,
        token=token,
        workspace=workspace,
    )
    runner.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
