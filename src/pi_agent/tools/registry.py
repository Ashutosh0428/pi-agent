"""Tool registry: holds the active tools and dispatches calls by name."""

from __future__ import annotations

from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool
from pi_agent.tools.datasci import data_tools
from pi_agent.tools.filesystem import filesystem_tools
from pi_agent.tools.planning import planning_tools
from pi_agent.tools.safe_exec import safe_command_tools
from pi_agent.tools.search import search_tools
from pi_agent.tools.shell import shell_tools
from pi_agent.tools.subagent import subagent_tools
from pi_agent.tools.vcs import git_tools
from pi_agent.tools.web import web_tools


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools = {tool.name: tool for tool in tools}

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        """Tool definitions to send to the model."""
        return [tool.to_schema() for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def without(self, name: str) -> "ToolRegistry":
        """Return a copy of this registry with ``name`` removed.

        Used to build a sub-agent's tools without ``delegate``, so sub-agents
        cannot recursively spawn more sub-agents (depth is capped at one).
        """
        return ToolRegistry([t for t in self._tools.values() if t.name != name])

    def run(self, name: str, args: dict[str, Any], sandbox: Sandbox) -> str:
        """Execute a tool by name, converting any error into a string result.

        Errors are returned (not raised) so the model can see what went wrong
        and recover, rather than crashing the loop.
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'."
        try:
            return tool.handler(args, sandbox)
        except Exception as exc:  # surface the failure back to the model
            return f"Error running {name}: {exc}"


def build_default_tools(
    enable_shell: bool = True,
    enable_safe_command: bool = False,
    enable_subagents: bool = False,
    enable_data: bool = False,
    enable_vcs: bool = False,
    enable_web: bool = False,
) -> ToolRegistry:
    """Assemble the default tool set.

    ``enable_shell`` adds the full ``run_bash`` (local/trusted use only).
    ``enable_safe_command`` adds the restricted, read-only ``run_command``
    (safe for public/untrusted contexts).
    ``enable_subagents`` adds ``delegate`` (the Agent runs a focused sub-agent
    sequentially).
    ``enable_data`` adds ``analyze_data`` + ``make_slides`` (need the [data]
    extra).
    ``enable_vcs`` adds the read-only ``git`` tool (local/trusted; inherits the
    real environment to find git).
    ``enable_web`` adds the SSRF-guarded ``web_fetch`` tool (local/trusted only).
    All are independent.
    """
    tools = [*planning_tools(), *filesystem_tools(), *search_tools()]
    if enable_shell:
        tools += shell_tools()
    if enable_safe_command:
        tools += safe_command_tools()
    if enable_subagents:
        tools += subagent_tools()
    if enable_data:
        tools += data_tools()
    if enable_vcs:
        tools += git_tools()
    if enable_web:
        tools += web_tools()
    return ToolRegistry(tools)
