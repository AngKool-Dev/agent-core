"""ARGUS Replay report formatting utilities."""

from typing import Any, Dict, List, Optional


def format_timeline_text(timeline: List[Any]) -> str:
    """Format timeline entries as text."""
    lines = []
    lines.append("TIMELINE")
    lines.append("-" * 60)

    for entry in timestamp, event_type, category, status in [
        (e.timestamp, e.event_type, e.category, e.status) for e in timeline
    ]:
        ts = _format_timestamp(timestamp)
        line = f"{ts} {event_type} ({category})"
        if status:
            line += f" [{status}]"
        lines.append(line)

    return "\n".join(lines)


def format_security_text(security_data: Dict[str, Any]) -> str:
    """Format security section as text."""
    lines = []
    lines.append("SECURITY EVENTS")
    lines.append("-" * 60)
    lines.append(f"Allowed: {security_data.get('allowed', 0)}")
    lines.append(f"Denied: {security_data.get('denied', 0)}")
    lines.append(f"Approvals: {security_data.get('approvals', 0)}")
    lines.append(f"Injection Events: {security_data.get('injection_events', 0)}")
    return "\n".join(lines)


def format_recovery_text(recovery_data: Dict[str, Any]) -> str:
    """Format recovery section as text."""
    lines = []
    lines.append("RECOVERY EVENTS")
    lines.append("-" * 60)
    lines.append(f"Failures: {recovery_data.get('failures', 0)}")
    lines.append(f"Strategies: {', '.join(recovery_data.get('strategies', []))}")
    lines.append(f"Retries: {recovery_data.get('retries', 0)}")
    return "\n".join(lines)


def format_consistency_text(consistency_data: Dict[str, Any]) -> str:
    """Format consistency section as text."""
    lines = []
    lines.append("CONSISTENCY CHECK")
    lines.append("-" * 60)
    lines.append(f"Status: {consistency_data.get('status', 'N/A')}")
    lines.append(f"Warnings: {consistency_data.get('warnings', 0)}")
    lines.append(f"Errors: {consistency_data.get('errors', 0)}")

    if consistency_data.get("issues"):
        lines.append("\nIssues:")
        for issue in consistency_data["issues"]:
            lines.append(f"  [{issue.get('severity', 'unknown')}] {issue.get('description', '')}")

    return "\n".join(lines)


def _format_timestamp(timestamp: float) -> str:
    """Format a timestamp for display."""
    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%H:%M:%S.%f")[:-3]
