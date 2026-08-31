"""Argus trace command - execution tracing and history."""

import json
from typing import List

from argus.events.correlation import get_correlation_tracker
from argus.events.trace_renderer import (
    get_capability_events,
    get_events_by_run,
    get_failed_events,
    get_mcp_events,
    get_recovery_events,
    get_security_events,
    render_chronological,
    render_json,
    render_summary,
    render_tree,
)


def handle(repl, args: List[str]) -> str:
    """Handle /trace command."""
    if not args:
        return _show_recent_traces(repl)

    sub = args[0]

    # New canonical event trace commands
    if sub == "--tree":
        return _show_trace_tree(repl, args[1:])
    elif sub == "--json":
        return _show_trace_json(repl, args[1:])
    elif sub == "--run":
        if len(args) < 2:
            return "Usage: /trace --run <run_id>"
        return _show_run_trace(repl, args[1])
    elif sub == "--errors":
        return _show_error_traces(repl)
    elif sub == "--security":
        return _show_security_traces(repl)
    elif sub == "--recovery":
        return _show_recovery_traces(repl)
    elif sub == "--mcp":
        return _show_mcp_traces(repl)
    elif sub == "--capability":
        if len(args) < 2:
            return "Usage: /trace --capability <capability_id>"
        return _show_capability_traces_new(repl, args[1])
    elif sub == "--summary":
        return _show_trace_summary(repl)

    # Legacy commands (preserved for backward compatibility)
    if sub == "recent":
        limit = int(args[1]) if len(args) > 1 else 10
        return _show_recent_traces(repl, limit=limit)
    elif sub == "capability":
        if len(args) < 2:
            return "Usage: /trace capability <capability_id>"
        return _show_capability_traces(repl, args[1])
    elif sub == "clear":
        return _clear_traces(repl)
    elif sub == "export":
        return _export_traces(repl, args[1] if len(args) > 1 else "trace_export.json")
    elif sub == "stats":
        return _show_trace_stats(repl)

    return f"Unknown trace command: {sub}"


def _get_redact_fn(repl):
    """Get redaction function from repl's secret manager."""
    if hasattr(repl, '_secret_manager') and repl._secret_manager:
        return repl._secret_manager.redact_dict
    return None


def _show_recent_traces(repl, limit: int = 10) -> str:
    """Show recent execution traces from canonical events."""
    tracker = get_correlation_tracker()
    events = list(tracker._events.values())

    if not events:
        # Fall back to legacy traces
        return _show_legacy_traces(repl, limit)

    # Sort by timestamp, most recent first
    events.sort(key=lambda e: e.timestamp, reverse=True)
    events = events[:limit]

    lines = [f"Recent execution traces (last {limit}):", "-" * 60]

    for event in events:
        status = "✓" if event.is_success else "✗" if event.is_failure else "•"
        line = f"  {status} [{event.event_type.value}]"

        if event.capability:
            line += f" capability={event.capability}"

        if event.duration:
            line += f" time={event.duration:.3f}s"

        if event.source.value:
            line += f" source={event.source.value}"

        lines.append(line)

        if event.metadata.get("error"):
            lines.append(f"    Error: {str(event.metadata['error'])[:80]}")

    return "\n".join(lines)


def _show_legacy_traces(repl, limit: int = 10) -> str:
    """Show legacy execution traces."""
    router = _get_cap_router(repl)

    lines = [f"Recent execution traces (last {limit}):", "-" * 60]

    all_history = []
    for cap_id, history in router._execution_history.items():
        for entry in history:
            all_history.append((cap_id, entry))

    if not all_history:
        lines.append("  No execution traces recorded.")
        lines.append("  Run some commands first to generate traces.")
        return "\n".join(lines)

    all_history.sort(key=lambda x: x[1].timestamp, reverse=True)

    for cap_id, entry in all_history[:limit]:
        status = "✓" if entry.success else "✗"
        lines.append(
            f"  {status} [{cap_id}] "
            f"time={entry.execution_time:.3f}s "
            f"backend={entry.backend}"
        )
        if entry.error:
            lines.append(f"    Error: {entry.error[:80]}")

    return "\n".join(lines)


def _show_trace_tree(repl, args: List[str]) -> str:
    """Show trace as a tree."""
    tracker = get_correlation_tracker()

    if args:
        run_id = args[0]
        events = get_events_by_run(tracker, run_id)
    else:
        events = list(tracker._events.values())

    redact_fn = _get_redact_fn(repl)
    return render_tree(events, redact_fn=redact_fn)


def _show_trace_json(repl, args: List[str]) -> str:
    """Show trace as JSON."""
    tracker = get_correlation_tracker()

    if args:
        run_id = args[0]
        events = get_events_by_run(tracker, run_id)
    else:
        events = list(tracker._events.values())

    redact_fn = _get_redact_fn(repl)
    return render_json(events, redact_fn=redact_fn)


def _show_run_trace(repl, run_id: str) -> str:
    """Show trace for a specific run."""
    tracker = get_correlation_tracker()
    events = get_events_by_run(tracker, run_id)

    if not events:
        return f"No events found for run: {run_id}"

    redact_fn = _get_redact_fn(repl)
    return render_chronological(events, redact_fn=redact_fn)


def _show_error_traces(repl) -> str:
    """Show error/failure traces."""
    tracker = get_correlation_tracker()
    events = get_failed_events(tracker)

    if not events:
        return "No error events recorded."

    redact_fn = _get_redact_fn(repl)
    return render_chronological(events, redact_fn=redact_fn)


def _show_security_traces(repl) -> str:
    """Show security-related traces."""
    tracker = get_correlation_tracker()
    events = get_security_events(tracker)

    if not events:
        return "No security events recorded."

    redact_fn = _get_redact_fn(repl)
    return render_chronological(events, redact_fn=redact_fn)


def _show_recovery_traces(repl) -> str:
    """Show recovery-related traces."""
    tracker = get_correlation_tracker()
    events = get_recovery_events(tracker)

    if not events:
        return "No recovery events recorded."

    redact_fn = _get_redact_fn(repl)
    return render_chronological(events, redact_fn=redact_fn)


def _show_mcp_traces(repl) -> str:
    """Show MCP-related traces."""
    tracker = get_correlation_tracker()
    events = get_mcp_events(tracker)

    if not events:
        return "No MCP events recorded."

    redact_fn = _get_redact_fn(repl)
    return render_chronological(events, redact_fn=redact_fn)


def _show_capability_traces_new(repl, capability: str) -> str:
    """Show traces for a specific capability."""
    tracker = get_correlation_tracker()
    events = get_capability_events(tracker, capability)

    if not events:
        return f"No events found for capability: {capability}"

    redact_fn = _get_redact_fn(repl)
    return render_chronological(events, redact_fn=redact_fn)


def _show_trace_summary(repl) -> str:
    """Show trace summary."""
    tracker = get_correlation_tracker()
    events = list(tracker._events.values())

    if not events:
        return "No events recorded."

    return render_summary(events)


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


def _show_capability_traces(repl, capability_id: str) -> str:
    """Show traces for a specific capability (legacy)."""
    router = _get_cap_router(repl)
    history = router.get_execution_history(capability_id, limit=20)

    if not history:
        return f"No traces found for capability: {capability_id}"

    lines = [f"Traces for {capability_id}:", "-" * 50]

    for entry in history:
        status = "✓" if entry.success else "✗"
        lines.append(
            f"  {status} time={entry.execution_time:.3f}s "
            f"backend={entry.backend} "
            f"fallback={entry.fallback_used}"
        )
        if entry.error:
            lines.append(f"    Error: {entry.error[:80]}")

    return "\n".join(lines)


def _clear_traces(repl) -> str:
    """Clear all execution traces."""
    router = _get_cap_router(repl)
    router.clear_history()

    # Also clear canonical events
    tracker = get_correlation_tracker()
    tracker.clear()

    return "Execution traces cleared."


def _export_traces(repl, filename: str) -> str:
    """Export traces to a JSON file."""
    tracker = get_correlation_tracker()
    events = list(tracker._events.values())

    if not events:
        # Fall back to legacy export
        return _export_legacy_traces(repl, filename)

    events.sort(key=lambda e: e.timestamp)
    redact_fn = _get_redact_fn(repl)

    export_data = {
        "events": [e.to_dict(redact_fn=redact_fn) for e in events],
        "total_events": len(events),
    }

    try:
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        return f"Traces exported to {filename}"
    except Exception as e:
        return f"Failed to export traces: {e}"


def _export_legacy_traces(repl, filename: str) -> str:
    """Export legacy traces to a JSON file."""
    router = _get_cap_router(repl)

    export_data = {}
    for cap_id, history in router._execution_history.items():
        export_data[cap_id] = [
            {
                "success": entry.success,
                "error": entry.error,
                "execution_time": entry.execution_time,
                "backend": entry.backend,
                "fallback_used": entry.fallback_used,
                "timestamp": entry.timestamp,
            }
            for entry in history
        ]

    try:
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        return f"Traces exported to {filename}"
    except Exception as e:
        return f"Failed to export traces: {e}"


def _show_trace_stats(repl) -> str:
    """Show trace statistics (legacy)."""
    router = _get_cap_router(repl)
    stats = router.get_statistics()

    if not stats:
        return "No trace statistics available."

    lines = ["Execution Statistics:", "-" * 60]
    lines.append(
        f"  {'Capability':<30} {'Total':>6} {'OK':>6} {'Fail':>6} "
        f"{'Rate':>6} {'Avg(s)':>8}"
    )
    lines.append("-" * 60)

    total_all = 0
    success_all = 0
    for cap_id, stat in stats.items():
        total_all += stat['total_executions']
        success_all += stat['successful']
        lines.append(
            f"  {cap_id:<30} {stat['total_executions']:>6} "
            f"{stat['successful']:>6} {stat['failed']:>6} "
            f"{stat['success_rate']:>5.1%} {stat['avg_execution_time']:>7.3f}"
        )

    lines.append("-" * 60)
    overall_rate = success_all / total_all if total_all > 0 else 0
    lines.append(
        f"  {'TOTAL':<30} {total_all:>6} {success_all:>6} "
        f"{total_all - success_all:>6} {overall_rate:>5.1%}"
    )

    return "\n".join(lines)
