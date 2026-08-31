"""Argus slash command registry."""

import os
from typing import Dict, List

from argus.commands.agent import handle as agent_handle
from argus.commands.capabilities import handle as capabilities_handle
from argus.commands.config import handle as config_handle
from argus.commands.doctor import handle as doctor_handle
from argus.commands.help import handle as help_handle
from argus.commands.memory import handle as memory_handle
from argus.commands.project import handle as project_handle
from argus.commands.reality import handle as reality_handle
from argus.commands.release import handle as release_handle
from argus.commands.replay import handle as replay_handle
from argus.commands.review import handle as review_handle
from argus.commands.session import handle as session_handle
from argus.commands.skills import handle as skills_handle
from argus.commands.subagents import handle as subagents_handle
from argus.commands.tools import handle as tools_handle
from argus.commands.trace import handle as trace_handle


_COMMAND_GROUPS = [
    {
        "name": "Agent",
        "commands": [
            ("agent", "agent", "Send a request to the agent (or just type naturally)"),
        ]
    },
    {
        "name": "Project",
        "commands": [
            ("project", "project", "Show project information"),
            ("clear", "clear", "Clear the screen"),
        ]
    },
    {
        "name": "Models",
        "commands": [
            ("model", "model", "Show or set model"),
            ("providers", "providers", "List model providers"),
            ("models", "models", "List available models"),
        ]
    },
    {
        "name": "Memory",
        "commands": [
            ("memory", "memory", "Memory operations (summary, search)"),
        ]
    },
    {
        "name": "Skills",
        "commands": [
            ("skills", "skills", "Skill operations (list, search, show)"),
        ]
    },
    {
        "name": "Session",
        "commands": [
            ("session", "session", "Session operations (new, list, save, delete)"),
        ]
    },
    {
        "name": "System",
        "commands": [
            ("config", "config", "Configuration (get, set, show)"),
            ("tools", "tools", "Tool operations (list, run)"),
            ("capabilities", "capabilities", "Capability operations (list, show, search, discover)"),
            ("doctor", "doctor", "System health check and diagnostics"),
            ("trace", "trace", "Execution tracing and history"),
            ("replay", "replay", "Run reconstruction and forensics"),
            ("review", "review", "Evidence-based review of completed work"),
            ("reality", "reality", "Production-reality qualification suite"),
            ("release", "release", "Release engineering qualification suite"),
            ("subagents", "subagents", "Subagent operations (list, show, create, cancel)"),
            ("help", "help", "Show this help"),
            ("exit", "exit", "Exit Argus (alias: quit)"),
        ]
    },
]


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, callable] = {}

    def register(self, name: str, handler: callable) -> None:
        self._commands[name] = handler

    def handle(self, name: str, repl, args: List[str]) -> str:
        handler = self._commands.get(name)
        if not handler:
            return f"Unknown command: /{name}"
        return handler(repl, args)


def build_registry() -> CommandRegistry:
    registry = CommandRegistry()
    registry.register("help", help_handle)
    registry.register("exit", _exit)
    registry.register("quit", _exit)
    registry.register("clear", _clear)
    registry.register("session", session_handle)
    registry.register("config", config_handle)
    registry.register("tools", tools_handle)
    registry.register("capabilities", capabilities_handle)
    registry.register("doctor", doctor_handle)
    registry.register("trace", trace_handle)
    registry.register("replay", replay_handle)
    registry.register("review", review_handle)
    registry.register("reality", reality_handle)
    registry.register("release", release_handle)
    registry.register("subagents", subagents_handle)
    registry.register("skills", skills_handle)
    registry.register("memory", memory_handle)
    registry.register("project", project_handle)
    registry.register("agent", agent_handle)
    return registry


def _exit(repl, args) -> str:
    raise SystemExit(0)


def _clear(repl, args) -> str:
    os.system("cls" if os.name == "nt" else "clear")
    return ""