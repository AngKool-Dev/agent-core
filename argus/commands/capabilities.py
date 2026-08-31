"""Argus capabilities command - list, discover, and inspect capabilities."""

import json
import shlex
from typing import List


def handle(repl, args: List[str]) -> str:
    """Handle /capabilities command."""
    if not args:
        return _list_capabilities(repl)

    sub = args[0]
    if sub == "list":
        return _list_capabilities(repl)
    elif sub == "show":
        if len(args) < 2:
            return "Usage: /capabilities show <capability_id>"
        return _show_capability(repl, args[1])
    elif sub == "search":
        if len(args) < 2:
            return "Usage: /capabilities search <query>"
        return _search_capabilities(repl, " ".join(args[1:]))
    elif sub == "types":
        return _list_types(repl)
    elif sub == "stats":
        return _show_stats(repl)
    elif sub == "discover":
        query = args[1] if len(args) > 1 else ""
        return _discover_capabilities(repl, query)

    return f"Unknown capabilities command: {sub}"


def _get_cap_router(repl):
    """Get or create the capability router from the repl."""
    if not hasattr(repl, "_cap_router") or repl._cap_router is None:
        from argus.capabilities import CapabilityRegistry, CapabilityRouter
        from argus.capabilities.adapter import register_default_tool_capabilities
        from argus.capabilities.model_registry import auto_register_model_capabilities

        registry = CapabilityRegistry()
        register_default_tool_capabilities(registry, repl.tool_registry)

        if hasattr(repl, 'model_router') and repl.model_router:
            provider_registry = repl.model_router._registry
            auto_register_model_capabilities(registry, provider_registry)

        repl._cap_router = CapabilityRouter(registry)
    return repl._cap_router


def _list_capabilities(repl) -> str:
    """List all capabilities."""
    router = _get_cap_router(repl)
    caps = router.discover_capabilities()

    if not caps:
        return "No capabilities registered. Use /capabilities discover to find capabilities."

    lines = ["Registered capabilities:", "-" * 60]
    for cap in caps:
        status = "✓" if cap["available"] else "✗"
        lines.append(f"  {status} {cap['id']:<30} {cap['type']:<12} {cap['name']}")
        lines.append(f"    {cap['description'][:60]}")

    return "\n".join(lines)


def _show_capability(repl, capability_id: str) -> str:
    """Show details of a specific capability."""
    router = _get_cap_router(repl)
    cap = router._registry.get(capability_id)

    if not cap:
        return f"Capability not found: {capability_id}"

    health = cap.health_check()
    lines = [
        f"Capability: {cap.get_id()}",
        f"Name: {cap.get_name()}",
        f"Type: {cap.get_type().value}",
        f"Description: {cap.get_description()}",
        f"Available: {cap.check_availability()}",
        f"Health: {health.get('status', 'unknown')}",
        f"Health Details: {json.dumps(health, indent=2)}",
    ]

    return "\n".join(lines)


def _search_capabilities(repl, query: str) -> str:
    """Search capabilities by query string."""
    router = _get_cap_router(repl)
    caps = router.discover_capabilities(query=query)

    if not caps:
        return f"No capabilities found matching: {query}"

    lines = [f"Search results for '{query}':", "-" * 40]
    for cap in caps:
        status = "✓" if cap["available"] else "✗"
        lines.append(f"  {status} {cap['id']:<30} {cap['name']}")

    return "\n".join(lines)


def _list_types(repl) -> str:
    """List capability types and counts."""
    from argus.capabilities import CapabilityType

    router = _get_cap_router(repl)
    lines = ["Capability types:", "-" * 30]

    for cap_type in CapabilityType:
        caps = router._registry.get_by_type(cap_type)
        lines.append(f"  {cap_type.value:<15} {len(caps)} capabilities")

    return "\n".join(lines)


def _show_stats(repl) -> str:
    """Show execution statistics."""
    router = _get_cap_router(repl)
    stats = router.get_statistics()

    if not stats:
        return "No execution statistics available."

    lines = ["Capability execution statistics:", "-" * 50]
    lines.append(f"  {'ID':<30} {'Total':>6} {'OK':>6} {'Fail':>6} {'Rate':>6} {'Avg(s)':>8}")
    lines.append("-" * 50)

    for cap_id, stat in stats.items():
        lines.append(
            f"  {cap_id:<30} {stat['total_executions']:>6} "
            f"{stat['successful']:>6} {stat['failed']:>6} "
            f"{stat['success_rate']:>5.1%} {stat['avg_execution_time']:>7.3f}"
        )

    return "\n".join(lines)


def _discover_capabilities(repl, query: str = "") -> str:
    """Discover available capabilities and refresh the registry."""
    router = _get_cap_router(repl)
    caps = router.discover_capabilities(query=query)

    if not caps:
        return "No capabilities discovered."

    lines = [f"Discovered capabilities:", "-" * 40]
    for cap in caps:
        status = "✓" if cap["available"] else "✗"
        lines.append(f"  {status} {cap['id']:<30} {cap['name']}")

    return "\n".join(lines)