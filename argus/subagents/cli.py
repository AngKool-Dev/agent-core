"""Subagents command for ARGUS."""

from typing import List

from argus.subagents import SubagentRole, SubagentTask, create_orchestrator


def handle(repl, args: List[str]) -> str:
    """Handle /subagents command."""
    if not args:
        return _list_subagents(repl)

    sub = args[0]

    if sub == "list":
        return _list_subagents(repl)

    elif sub == "show":
        if len(args) < 2:
            return "Usage: /subagents show <id>"
        return _show_subagent(repl, args[1])

    elif sub == "cancel":
        if len(args) < 2:
            return "Usage: /subagents cancel <id>"
        return _cancel_subagent(repl, args[1])

    elif sub == "tree":
        if len(args) < 2:
            return "Usage: /subagents tree <id>"
        return _show_tree(repl, args[1])

    elif sub == "create":
        if len(args) < 3:
            return "Usage: /subagents create <role> <objective>"
        role_str = args[1].upper()
        objective = " ".join(args[2:])
        try:
            role = SubagentRole(role_str.lower())
        except ValueError:
            return f"Unknown role: {role_str}"
        return _create_subagent(repl, role, objective)

    elif sub == "help":
        return _show_help()

    return f"Unknown subagents command: {sub}"


def _get_orchestrator(repl):
    """Get or create the orchestrator from the repl."""
    if not hasattr(repl, "_subagent_orchestrator") or repl._subagent_orchestrator is None:
        repl._subagent_orchestrator = create_orchestrator()
    return repl._subagent_orchestrator


def _list_subagents(repl) -> str:
    """List all subagents."""
    orchestrator = _get_orchestrator(repl)
    subagents = orchestrator.manager.list()

    if not subagents:
        return "No subagents."

    from argus.subagents.report import format_subagents_text
    return format_subagents_text(subagents)


def _show_subagent(repl, subagent_id: str) -> str:
    """Show details of a specific subagent."""
    orchestrator = _get_orchestrator(repl)
    subagent = orchestrator.manager.get(subagent_id)

    if not subagent:
        return f"Subagent not found: {subagent_id}"

    lines = [
        f"Subagent: {subagent.id}",
        f"Role: {subagent.role.value}",
        f"Status: {subagent.status.value}",
        f"Objective: {subagent.objective}",
        "",
        f"Parent Run: {subagent.parent_run_id}",
        f"Parent Task: {subagent.parent_task_id}",
        f"Parent ID: {subagent.parent_id}",
        "",
        "Budget:",
    ]

    if subagent.budget:
        for key, value in subagent.budget.items():
            used = subagent.budget_used.get(key, 0)
            lines.append(f"  {key}: {used}/{value}")

    if subagent.result:
        lines.append("")
        lines.append("Result:")
        lines.append(f"  {subagent.result.get('summary', 'No summary')}")

    if subagent.error:
        lines.append("")
        lines.append(f"Error: {subagent.error}")

    return "\n".join(lines)


def _cancel_subagent(repl, subagent_id: str) -> str:
    """Cancel a subagent."""
    orchestrator = _get_orchestrator(repl)
    if orchestrator.cancel(subagent_id):
        return f"Subagent {subagent_id} cancelled."
    return f"Failed to cancel subagent: {subagent_id}"


def _show_tree(repl, subagent_id: str) -> str:
    """Show subagent tree."""
    orchestrator = _get_orchestrator(repl)
    tree = orchestrator.get_tree(subagent_id)

    if not tree:
        return f"Subagent not found: {subagent_id}"

    from argus.subagents.report import format_subagent_tree
    subagent = orchestrator.manager.get(subagent_id)
    if subagent:
        return format_subagent_tree(subagent, orchestrator.manager)

    return "Subagent not found."


def _create_subagent(repl, role: SubagentRole, objective: str) -> str:
    """Create a new subagent."""
    orchestrator = _get_orchestrator(repl)

    # Get parent run ID from repl if available
    parent_run_id = getattr(repl, "_run_id", "")

    subagent = orchestrator.delegate(
        objective=objective,
        role=role,
        parent_run_id=parent_run_id,
    )

    return f"Created subagent: {subagent.id} ({role.value})"


def _show_help() -> str:
    """Show subagents command help."""
    return """Subagents command help:
/subagents                    List all subagents
/subagents list               List all subagents
/subagents show <id>          Show subagent details
/subagents cancel <id>        Cancel a subagent
/subagents tree <id>          Show subagent tree
/subagents create <role> <objective>  Create a new subagent
/subagents help               Show this help

Roles: researcher, implementer, tester, reviewer, debugger
"""
