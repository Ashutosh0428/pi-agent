"""MCP stdio client tests against a scripted fake server (no network).

The fake server is a tiny inline python script speaking JSON-RPC over stdio,
so these tests exercise the real subprocess/handshake/framing path without any
external MCP server installed.
"""

from __future__ import annotations

import sys
import textwrap

from pi_agent.mcp_client import (
    MCPServer,
    load_mcp_servers,
    mcp_tools,
    start_mcp_servers,
)

# A minimal MCP server: handshake, two tools (one paginated across two list
# pages), an echo tool, and an error tool.
FAKE_SERVER = textwrap.dedent(
    """
    import json, sys
    def send(obj): sys.stdout.write(json.dumps(obj) + "\\n"); sys.stdout.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        msg = json.loads(line)
        mid, method = msg.get("id"), msg.get("method")
        if method == "initialize":
            send({"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":"2025-06-18",
                  "capabilities":{"tools":{}},"serverInfo":{"name":"fake","version":"1"}}})
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            cursor = (msg.get("params") or {}).get("cursor")
            if not cursor:
                send({"jsonrpc":"2.0","id":mid,"result":{"tools":[
                    {"name":"echo","description":"Echo text",
                     "inputSchema":{"type":"object","properties":{"text":{"type":"string"}}}}],
                    "nextCursor":"page2"}})
            else:
                send({"jsonrpc":"2.0","id":mid,"result":{"tools":[
                    {"name":"boom","description":"Always errors",
                     "inputSchema":{"type":"object"}}]}})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            if name == "echo":
                txt = params.get("arguments", {}).get("text", "")
                send({"jsonrpc":"2.0","id":mid,"result":{"content":[{"type":"text","text":"echo: "+txt}],
                      "isError":False}})
            elif name == "boom":
                send({"jsonrpc":"2.0","id":mid,"result":{"content":[{"type":"text","text":"kaboom"}],
                      "isError":True}})
            else:
                send({"jsonrpc":"2.0","id":mid,"error":{"code":-32602,"message":"unknown tool"}})
    """
)


def _fake_server() -> MCPServer:
    return MCPServer(name="fake", command=sys.executable, args=["-c", FAKE_SERVER])


class TestHandshakeAndTools:
    def test_start_lists_paginated_tools(self):
        srv = _fake_server()
        srv.start()
        try:
            names = {t["name"] for t in srv.tools}
            assert names == {"echo", "boom"}  # both pages merged
        finally:
            srv.close()

    def test_call_tool_returns_text(self):
        srv = _fake_server()
        srv.start()
        try:
            assert srv.call_tool("echo", {"text": "hi"}) == "echo: hi"
        finally:
            srv.close()

    def test_is_error_surfaced_as_error_string(self):
        srv = _fake_server()
        srv.start()
        try:
            out = srv.call_tool("boom", {})
            assert out.startswith("Error from MCP tool")
        finally:
            srv.close()


class TestToolWrapping:
    def test_tools_are_namespaced_and_mutating(self):
        srv = _fake_server()
        srv.start()
        try:
            tools = mcp_tools([srv])
            names = {t.name for t in tools}
            assert "mcp__fake__echo" in names
            assert all(t.mutating for t in tools)  # confirmation gate
            echo = next(t for t in tools if t.name == "mcp__fake__echo")
            assert echo.handler({"text": "yo"}, None) == "echo: yo"
            assert echo.description.startswith("[mcp:fake]")
        finally:
            srv.close()


class TestConfigLoading:
    def test_missing_config_returns_empty(self, tmp_path):
        assert load_mcp_servers(str(tmp_path / "nope.json")) == []

    def test_parses_mcpservers_shape(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(
            '{"mcpServers": {"gh": {"command": "echo", "args": ["x"], "env": {"K": "v"}}}}'
        )
        servers = load_mcp_servers(str(cfg))
        assert len(servers) == 1
        assert servers[0].name == "gh"
        assert servers[0].command == "echo"
        assert servers[0].env == {"K": "v"}

    def test_bad_server_skipped_not_crashing(self):
        good = _fake_server()
        bad = MCPServer(name="bad", command="this-binary-does-not-exist-xyz")
        live = start_mcp_servers([good, bad])
        try:
            assert {s.name for s in live} == {"fake"}  # bad one skipped
        finally:
            for s in live:
                s.close()
