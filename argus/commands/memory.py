"""Argus memory command."""

from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /memory <summary|search> [args]"

    sub = args[0]
    if sub == "summary":
        if not repl.agent.memory.available:
            return "Memory is not configured"
        summary = repl.agent.memory.retrieve_relevant("")
        if not summary:
            return "No project memory found"
        return summary

    elif sub == "search":
        query = args[1] if len(args) > 1 else ""
        if not query:
            return "Usage: /memory search <query>"
        if not repl.agent.memory.available:
            return "Memory is not configured"
        entries = repl.agent.memory.search(query)
        if not entries:
            return f"No memory entries found for: {query}"
        lines = [f"Memory entries for '{query}':"]
        for entry in entries:
            etype = entry.get("type", "")
            summary = entry.get("summary", entry.get("content", ""))
            lines.append(f"  [{etype}] {summary}")
        return "\n".join(lines)

    return f"Unknown memory command: {sub}"
