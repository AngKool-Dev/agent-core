"""Argus skills command."""

from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /skills <list|search|show> [args]"

    sub = args[0]
    if sub == "list":
        skills = repl.agent._skill_registry.list()
        if not skills:
            return "No skills discovered. Add skill directories to config or place them in built-in skills."
        lines = ["Discovered skills:"]
        for skill in skills:
            triggers = ", ".join(skill.triggers) if skill.triggers else "none"
            lines.append(f"  {skill.name:<20} triggers: {triggers}")
            lines.append(f"    {skill.description}")
        return "\n".join(lines)

    elif sub == "search":
        query = args[1] if len(args) > 1 else ""
        if not query:
            return "Usage: /skills search <query>"
        matches = repl.agent._skill_registry.search(query)
        if not matches:
            return f"No skills matched: {query}"
        lines = [f"Skills matching '{query}':"]
        for skill in matches:
            lines.append(f"  {skill.name}: {skill.description}")
        return "\n".join(lines)

    elif sub == "show":
        name = args[1] if len(args) > 1 else None
        if not name:
            return "Usage: /skills show <name>"
        skill = repl.agent._skill_registry.get(name)
        if not skill:
            return f"Skill not found: {name}"
        lines = [
            f"Name: {skill.name}",
            f"Description: {skill.description}",
            f"Triggers: {', '.join(skill.triggers) if skill.triggers else 'none'}",
            f"Path: {skill.path}",
            "",
            "Instructions:",
            skill.instructions,
        ]
        return "\n".join(lines)

    return f"Unknown skills command: {sub}"
