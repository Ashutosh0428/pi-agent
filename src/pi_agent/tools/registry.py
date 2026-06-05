"""Tool registry: holds the active tools and dispatches calls by name."""

from __future__ import annotations

from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool
from pi_agent.tools.filesystem import filesystem_tools
from pi_agent.tools.planning import planning_tools
from pi_agent.tools.safe_exec import safe_command_tools
from pi_agent.tools.search import search_tools
from pi_agent.tools.shell import shell_tools


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
    enable_shell: bool = True, enable_safe_command: bool = False
) -> ToolRegistry:
    """Assemble the default tool set.

    ``enable_shell`` adds the full ``run_bash`` (local/trusted use only).
    ``enable_safe_command`` adds the restricted, read-only ``run_command``
    (safe for public/untrusted contexts). They are independent.
    """
    tools = [*planning_tools(), *filesystem_tools(), *search_tools()]
    if enable_shell:
        tools += shell_tools()
    if enable_safe_command:
        tools += safe_command_tools()
    return ToolRegistry(tools)
