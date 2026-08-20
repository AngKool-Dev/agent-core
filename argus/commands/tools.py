"""Argus tools command."""

import shlex
from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /tools <list|run> [args]"

    sub = args[0]
    if sub == "list":
        tools = repl.tool_registry.list_tools()
        lines = ["Available tools:"]
        for tool in tools:
            lines.append(f"  {tool['name']:<20} {tool['description']}")
        return "\n".join(lines)

    elif sub == "run":
        if len(args) < 2:
            return "Usage: /tools run <name> <args>"
        name = args[1]
        tool_args = " ".join(args[2:])

        try:
            parsed = shlex.split(tool_args)
            kwargs = {}
            for item in parsed:
                if "=" in item:
                    k, v = item.split("=", 1)
                    kwargs[k] = v
                else:
                    kwargs.setdefault("args", [])
                    kwargs["args"].append(item)
        except Exception as e:
            return f"Error parsing tool args: {e}"

        result = repl.tool_registry.execute(name, **kwargs)
        if result.success:
            return result.output
        return f"Error: {result.error}"

    return f"Unknown tools command: {sub}"
