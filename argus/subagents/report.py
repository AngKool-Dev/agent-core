"""Subagent reporting for ARGUS."""

from typing import Any, Dict, List

from argus.subagents.models import Subagent, SubagentStatus


def format_subagents_text(subagents: List[Subagent]) -> str:
    """Format a list of subagents as human-readable text."""
    if not subagents:
        return "No subagents."

    lines = [
        "ARGUS SUBAGENTS",
        "─" * 60,
        "",
    ]

    # Header
    lines.append(
        f"{'ID':<10} {'ROLE':<15} {'STATUS':<15} {'BUDGET':<20}"
    )
    lines.append("─" * 60)

    # Subagent rows
    for subagent in subagents:
        budget_str = ""
        if subagent.budget_used:
            model_calls = subagent.budget_used.get("model_calls", 0)
            max_calls = subagent.budget.get("max_model_calls", "?")
            budget_str = f"{model_calls}/{max_calls} calls"

        lines.append(
            f"{str(subagent.id):<10} {subagent.role.value:<15} "
            f"{subagent.status.value:<15} {budget_str:<20}"
        )

    lines.append("")
    lines.append(f"Total: {len(subagents)}")
    lines.append(f"Active: {sum(1 for s in subagents if s.is_active)}")
    lines.append(f"Completed: {sum(1 for s in subagents if s.status == SubagentStatus.COMPLETED)}")

    return "\n".join(lines)


def format_subagent_tree(subagent: Subagent, manager: Any, indent: int = 0) -> str:
    """Format a subagent and its children as a tree."""
    prefix = "  " * indent
    connector = "├── " if indent > 0 else ""

    lines = [
        f"{prefix}{connector}{subagent.role.value} ({subagent.status.value})"
    ]

    if subagent.objective:
        lines.append(f"{prefix}  Objective: {subagent.objective}")

    # Add children
    for child_id in subagent.child_ids:
        child = manager.get(child_id)
        if child:
            lines.append(format_subagent_tree(child, manager, indent + 1))

    return "\n".join(lines)
