"""Argus help command with categorized output."""

from typing import List


def handle(repl, args: List[str]) -> str:
    from argus.commands import _COMMAND_GROUPS

    sub = args[0] if args else ""
    if sub in ("full", "verbose", "-full", "-verbose"):
        return _format_full_help(_COMMAND_GROUPS)
    return _format_short_help(_COMMAND_GROUPS)


def _format_short_help(groups) -> str:
    lines = ["Available commands:"]
    for grp in groups:
        for cmd, name, desc in grp["commands"]:
            lines.append(f"  /{name:<18} {desc}")
    return "\n".join(lines)


def _format_full_help(groups) -> str:
    lines = []
    for grp in groups:
        lines.append(grp["name"] + ":")
        for cmd, name, desc in grp["commands"]:
            lines.append(f"  /{name:<18} {desc}")
        lines.append("")
    lines.append("Tip: Type natural language to run the agent directly.")
    return "\n".join(lines)
