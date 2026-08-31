"""Argus doctor command - system health check and diagnostics."""

import json
import os
import platform
import sys
from typing import List


def handle(repl, args: List[str]) -> str:
    """Handle /doctor command."""
    if not args:
        return _run_full_diagnostic(repl)

    sub = args[0]
    if sub == "full":
        return _run_full_diagnostic(repl)
    elif sub == "capabilities":
        return _check_capabilities(repl)
    elif sub == "models":
        return _check_models(repl)
    elif sub == "tools":
        return _check_tools(repl)
    elif sub == "system":
        return _check_system(repl)

    return f"Unknown doctor command: {sub}"


def _run_full_diagnostic(repl) -> str:
    """Run a full system diagnostic."""
    lines = [
        "=" * 60,
        "ARGUS SYSTEM DIAGNOSTIC",
        "=" * 60,
        "",
    ]

    # System info
    lines.extend(_get_system_info())
    lines.append("")

    # Tools check
    lines.extend(_get_tools_status(repl))
    lines.append("")

    # Capabilities check
    lines.extend(_get_capabilities_status(repl))
    lines.append("")

    # Models check
    lines.extend(_get_models_status(repl))
    lines.append("")

    # Summary
    lines.append("=" * 60)
    lines.append("DIAGNOSTIC COMPLETE")
    lines.append("=" * 60)

    return "\n".join(lines)


def _get_system_info() -> List[str]:
    """Get system information."""
    lines = ["System Information:", "-" * 30]
    lines.append(f"  Python: {sys.version.split()[0]}")
    lines.append(f"  Platform: {platform.system()} {platform.release()}")
    lines.append(f"  Architecture: {platform.machine()}")
    lines.append(f"  Working Directory: {os.getcwd()}")

    # Check for common tools
    tools_to_check = ["git", "node", "npm", "cargo", "rustc"]
    lines.append("  External tools:")
    for tool in tools_to_check:
        found = _check_command_exists(tool)
        status = "✓" if found else "✗"
        lines.append(f"    {status} {tool}")

    return lines


def _check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    import shutil
    return shutil.which(command) is not None


def _get_tools_status(repl) -> List[str]:
    """Get tools status."""
    lines = ["Tools Status:", "-" * 30]

    if not hasattr(repl, 'tool_registry'):
        lines.append("  Tool registry not available")
        return lines

    tools = repl.tool_registry.list_tools()
    lines.append(f"  Registered tools: {len(tools)}")

    for tool in tools:
        lines.append(f"    ✓ {tool['name']:<20} {tool['description'][:40]}")

    return lines


def _get_capabilities_status(repl) -> List[str]:
    """Get capabilities status."""
    lines = ["Capabilities Status:", "-" * 30]

    if not hasattr(repl, '_cap_router') or repl._cap_router is None:
        lines.append("  Capability router not initialized")
        lines.append("  Run /capabilities list to initialize")
        return lines

    router = repl._cap_router
    caps = router.discover_capabilities()
    available = sum(1 for c in caps if c["available"])
    healthy = sum(1 for c in caps if c["health"].get("status") == "healthy")

    lines.append(f"  Total capabilities: {len(caps)}")
    lines.append(f"  Available: {available}")
    lines.append(f"  Healthy: {healthy}")

    # Show unhealthy ones
    unhealthy = [c for c in caps if c["health"].get("status") != "healthy"]
    if unhealthy:
        lines.append("  Unhealthy capabilities:")
        for cap in unhealthy:
            lines.append(f"    ✗ {cap['id']}: {cap['health'].get('message', 'unknown')}")

    return lines


def _get_models_status(repl) -> List[str]:
    """Get model providers status."""
    lines = ["Model Providers Status:", "-" * 30]

    if not hasattr(repl, 'model_router') or repl.model_router is None:
        lines.append("  Model router not available")
        return lines

    router = repl.model_router
    registry = router._registry
    states = registry.list_states()

    lines.append(f"  Registered providers: {len(states)}")

    for state in states:
        name = state.capability.name
        available = registry.available(name)
        status = "✓" if available else "✗"
        models = ", ".join(state.capability.models[:3])
        lines.append(f"  {status} {name:<20} models: {models}")

    return lines


def _check_capabilities(repl) -> str:
    """Check capabilities health."""
    lines = ["Capabilities Health Check:", "-" * 40]

    if not hasattr(repl, '_cap_router') or repl._cap_router is None:
        lines.append("  Capability router not initialized")
        return "\n".join(lines)

    router = repl._cap_router
    health = router.get_health_status()

    for cap_id, info in health.items():
        status = "✓" if info["available"] else "✗"
        health_status = info["health"].get("status", "unknown")
        lines.append(f"  {status} {cap_id:<30} health: {health_status}")

    return "\n".join(lines)


def _check_models(repl) -> str:
    """Check model providers health."""
    lines = ["Model Providers Health Check:", "-" * 40]

    if not hasattr(repl, 'model_router') or repl.model_router is None:
        lines.append("  Model router not available")
        return "\n".join(lines)

    router = repl.model_router
    registry = router._registry
    states = registry.list_states()

    for state in states:
        name = state.capability.name
        provider = state.provider
        available = registry.available(name)

        status = "✓" if available else "✗"
        lines.append(f"  {status} {name}")

        if provider and hasattr(provider, 'health'):
            try:
                health = provider.health()
                lines.append(f"    Health: {health}")
            except Exception as e:
                lines.append(f"    Health check failed: {e}")

    return "\n".join(lines)


def _check_tools(repl) -> str:
    """Check tools health."""
    lines = ["Tools Health Check:", "-" * 30]

    if not hasattr(repl, 'tool_registry'):
        lines.append("  Tool registry not available")
        return "\n".join(lines)

    tools = repl.tool_registry.list_tools()
    for tool in tools:
        lines.append(f"  ✓ {tool['name']:<20} {tool['description'][:40]}")

    return "\n".join(lines)


def _check_system(repl) -> str:
    """Check system health."""
    lines = ["System Health:", "-" * 20]
    lines.append(f"  Python: {sys.version.split()[0]}")
    lines.append(f"  Platform: {platform.system()} {platform.release()}")
    lines.append(f"  CWD: {os.getcwd()}")

    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(os.getcwd())
        lines.append(f"  Disk: {free / (1024**3):.1f} GB free / {total / (1024**3):.1f} GB total")
    except Exception:
        pass

    return "\n".join(lines)