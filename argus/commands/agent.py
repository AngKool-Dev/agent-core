"""Argus agent command."""

from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /agent <request>"

    request = " ".join(args)
    try:
        from argus.formatter import format_agent_result

        result = repl.agent.execute(request)
        return format_agent_result(result, repl.verbose)
    except Exception as e:
        return f"Agent error: {e}"
