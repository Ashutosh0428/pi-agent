"""A minimal MCP (Model Context Protocol) stdio client — standard library only.

MCP is JSON-RPC 2.0 over a subprocess's stdin/stdout (newline-delimited). This
module spawns a configured server, performs the ``initialize`` handshake,
discovers its tools, and exposes each one as a pi :class:`~pi_agent.tools.base.Tool`
named ``mcp__<server>__<tool>``. That means any of the hundreds of existing MCP
servers (GitHub, Postgres, Slack, filesystem, …) becomes a pi tool with no code.

We implement the wire protocol directly rather than depend on the official
``mcp`` SDK (which pulls in anyio, httpx, starlette, …) — keeping pi's
"minimal, few dependencies" promise. Only the stdio transport and the tools
primitive are supported (not HTTP, resources, or prompts).

Config uses the de-facto ``mcpServers`` JSON shape shared by Claude Desktop,
Cursor and VS Code, so users paste their existing config unchanged::

    {"mcpServers": {"github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"],
                               "env": {"GITHUB_TOKEN": "..."}}}}
"""

from __future__ import annotations

import contextlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pi_agent.tools.base import Tool


def _log(message: str) -> None:
    """Status line to stderr (never stdout — that would corrupt one-shot output)."""
    print(message, file=sys.stderr)


PROTOCOL_VERSION = "2025-06-18"
_DEFAULT_TIMEOUT = 30.0
_NAME_SANITIZE = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass
class MCPServer:
    """One MCP server subprocess speaking JSON-RPC over stdio."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    _proc: subprocess.Popen | None = field(default=None, repr=False)
    _responses: queue.Queue = field(default_factory=queue.Queue, repr=False)
    _next_id: int = field(default=0, repr=False)
    _reader: threading.Thread | None = field(default=None, repr=False)
    tools: list[dict[str, Any]] = field(default_factory=list, repr=False)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Spawn the subprocess and run the MCP initialize handshake."""
        full_env = {**os.environ, **self.env}
        self._proc = subprocess.Popen(  # noqa: S603 - command comes from user's own config
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=full_env,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pi-agent", "version": _pi_version()},
            },
        )
        self._notify("notifications/initialized")
        self.tools = self._list_tools()

    def close(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            with contextlib.suppress(Exception):
                proc.terminate()
                proc.wait(timeout=2)
        self._proc = None

    # -- protocol -----------------------------------------------------------
    def _read_loop(self) -> None:
        """Background: push every JSON line the server prints onto the queue."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(json.JSONDecodeError):
                self._responses.put(json.loads(line))

    def _send(self, message: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise MCPError(f"server '{self.name}' is not running")
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _request(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = _DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        self._next_id += 1
        req_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        # Read framed messages until the one matching our id arrives. Notifications
        # and other-id responses are skipped (re-queued is unnecessary: ids are
        # monotonic and we await them in order).
        deadline_q = self._responses
        while True:
            try:
                msg = deadline_q.get(timeout=timeout)
            except queue.Empty as exc:
                raise MCPError(f"server '{self.name}' timed out on {method}") from exc
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                raise MCPError(f"{method}: {msg['error'].get('message', msg['error'])}")
            return msg.get("result", {})

    def _list_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params = {"cursor": cursor} if cursor else {}
            result = self._request("tools/list", params)
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Invoke a server tool; return its text content (or an error string)."""
        result = self._request("tools/call", {"name": tool_name, "arguments": arguments})
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        body = "\n".join(t for t in texts if t)
        if not body and result.get("structuredContent") is not None:
            body = json.dumps(result["structuredContent"])
        if result.get("isError"):
            return f"Error from MCP tool '{tool_name}': {body or 'tool reported an error'}"
        return body or "(no content)"


class MCPError(Exception):
    """An MCP transport or protocol failure."""


def load_mcp_servers(explicit_path: str | None = None) -> list[MCPServer]:
    """Parse an ``mcpServers`` config into (unstarted) :class:`MCPServer` objects.

    Looks at ``explicit_path``, else ``.pi/mcp.json`` in the cwd, else
    ``~/.pi/mcp.json``. Missing/invalid config returns an empty list.
    """
    path = _resolve_config_path(explicit_path)
    if path is None:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    servers = []
    for name, spec in (data.get("mcpServers") or {}).items():
        command = spec.get("command")
        if not command:
            continue
        servers.append(
            MCPServer(
                name=name,
                command=command,
                args=list(spec.get("args", [])),
                env=dict(spec.get("env", {})),
            )
        )
    return servers


def start_mcp_servers(servers: list[MCPServer]) -> list[MCPServer]:
    """Start each server; skip (with a warning) any that fail. Returns the live ones."""
    live = []
    for server in servers:
        try:
            server.start()
            live.append(server)
            _log(f"🔌 MCP: connected '{server.name}' ({len(server.tools)} tools)")
        except (MCPError, OSError, FileNotFoundError) as exc:
            _log(f"⚠️ MCP: skipped '{server.name}' — {type(exc).__name__}: {exc}")
    return live


def mcp_tools(servers: list[MCPServer]) -> list[Tool]:
    """Expose every started server's tools as pi Tools (mcp__<server>__<tool>)."""
    tools: list[Tool] = []
    for server in servers:
        for spec in server.tools:
            tools.append(_wrap(server, spec))
    return tools


def _wrap(server: MCPServer, spec: dict[str, Any]) -> Tool:
    raw_name = spec.get("name", "tool")
    safe = f"mcp__{_NAME_SANITIZE.sub('_', server.name)}__{_NAME_SANITIZE.sub('_', raw_name)}"
    description = f"[mcp:{server.name}] {spec.get('description', raw_name)}"
    schema = spec.get("inputSchema") or {"type": "object"}

    def handler(
        args: dict[str, Any], _sandbox: Any, _srv: MCPServer = server, _t: str = raw_name
    ) -> str:
        return _srv.call_tool(_t, args)

    return Tool(
        name=safe,
        description=description,
        input_schema=schema,
        handler=handler,
        mutating=True,  # spec's human-in-the-loop SHOULD: confirm MCP calls
    )


# -- small helpers (kept here so the module has no extra imports) -----------
def _resolve_config_path(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    for candidate in (Path(".pi/mcp.json"), Path.home() / ".pi/mcp.json"):
        if candidate.is_file():
            return candidate
    return None


def _pi_version() -> str:
    from pi_agent import __version__

    return __version__
