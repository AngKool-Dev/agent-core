"""Trace renderer for ARGUS."""

import json
from typing import Any, Dict, List, Optional

from argus.events.correlation import CorrelationTracker
from argus.events.event import AgentEvent
from argus.events.filters import (
    FailureFilter,
    MCPFilter,
    RecoveryFilter,
    RunFilter,
    SecurityFilter,
)
from argus.events.types import EventType


def format_timestamp(ts: float, base_ts: Optional[float] = None) -> str:
    """Format timestamp relative to base."""
    if base_ts is None:
        return f"{ts:.3f}"
    elapsed = ts - base_ts
    minutes = int(elapsed // 60)
    seconds = elapsed % 60
    return f"{minutes:02d}:{seconds:05.2f}"


def render_chronological(events: List[AgentEvent], redact_fn=None) -> str:
    """Render events in chronological order."""
    if not events:
        return "No events recorded."

    events = sorted(events, key=lambda e: e.timestamp)
    base_ts = events[0].timestamp

    lines = ["ARGUS TRACE", "-" * 60]

    for event in events:
        ts = format_timestamp(event.timestamp, base_ts)
        status_icon = "✓" if event.is_success else "✗" if event.is_failure else "•"
        line = f"{ts}  {status_icon} {event.event_type.value}"

        if event.capability:
            line += f"  [{event.capability}]"

        if event.status.value != "completed":
            line += f"  ({event.status.value})"

        if event.duration:
            line += f"  {event.duration:.3f}s"

        lines.append(line)

    return "\n".join(lines)


def render_tree(events: List[AgentEvent], redact_fn=None) -> str:
    """Render events as a tree structure."""
    if not events:
        return "No events recorded."

    events = sorted(events, key=lambda e: e.timestamp)

    # Build parent-child relationships
    event_map = {e.event_id: e for e in events}
    children: Dict[str, List[str]] = {}
    roots = []

    for event in events:
        if event.parent_event_id and event.parent_event_id in event_map:
            if event.parent_event_id not in children:
                children[event.parent_event_id] = []
            children[event.parent_event_id].append(event.event_id)
        else:
            roots.append(event.event_id)

    lines = ["ARGUS TRACE TREE", "-" * 60]

    def render_node(event_id: str, prefix: str = "", is_last: bool = True) -> None:
        event = event_map.get(event_id)
        if not event:
            return

        connector = "└── " if is_last else "├── "
        line = f"{prefix}{connector}{event.event_type.value}"

        if event.capability:
            line += f"  [{event.capability}]"

        if event.status.value != "completed":
            line += f"  ({event.status.value})"

        lines.append(line)

        child_ids = children.get(event_id, [])
        for i, child_id in enumerate(child_ids):
            is_last_child = i == len(child_ids) - 1
            child_prefix = prefix + ("    " if is_last else "│   ")
            render_node(child_id, child_prefix, is_last_child)

    for i, root_id in enumerate(roots):
        is_last = i == len(roots) - 1
        render_node(root_id, "", is_last)

    return "\n".join(lines)


def render_json(events: List[AgentEvent], redact_fn=None) -> str:
    """Render events as JSON."""
    if not events:
        return "[]"

    events = sorted(events, key=lambda e: e.timestamp)
    data = [e.to_dict(redact_fn=redact_fn) for e in events]
    return json.dumps(data, indent=2, default=str)


def render_summary(events: List[AgentEvent]) -> str:
    """Render a summary of events."""
    if not events:
        return "No events recorded."

    events = sorted(events, key=lambda e: e.timestamp)
    base_ts = events[0].timestamp
    end_ts = events[-1].timestamp
    duration = end_ts - base_ts

    # Count by category
    categories: Dict[str, int] = {}
    for event in events:
        cat = event.category
        categories[cat] = categories.get(cat, 0) + 1

    # Count successes/failures
    successes = sum(1 for e in events if e.is_success)
    failures = sum(1 for e in events if e.is_failure)

    lines = [
        "ARGUS TRACE SUMMARY",
        "-" * 60,
        f"  Total events: {len(events)}",
        f"  Duration: {duration:.3f}s",
        f"  Successes: {successes}",
        f"  Failures: {failures}",
        "",
        "  Events by category:",
    ]

    for cat, count in sorted(categories.items()):
        lines.append(f"    {cat}: {count}")

    return "\n".join(lines)


def get_events_by_run(tracker: CorrelationTracker, run_id: str) -> List[AgentEvent]:
    """Get all events for a run."""
    return tracker.get_run_events(run_id)


def get_events_by_session(tracker: CorrelationTracker, session_id: str) -> List[AgentEvent]:
    """Get all events for a session."""
    return tracker.get_session_events(session_id)


def get_security_events(tracker: CorrelationTracker, run_id: Optional[str] = None) -> List[AgentEvent]:
    """Get security events."""
    events = tracker.get_run_events(run_id) if run_id else list(tracker._events.values())
    security_types = {
        EventType.SECURITY_ALLOWED,
        EventType.SECURITY_DENIED,
        EventType.SECURITY_APPROVAL_REQUESTED,
        EventType.SECURITY_APPROVED,
        EventType.SECURITY_REJECTED,
        EventType.SECURITY_INJECTION_DETECTED,
    }
    return [e for e in events if e.event_type in security_types]


def get_recovery_events(tracker: CorrelationTracker, run_id: Optional[str] = None) -> List[AgentEvent]:
    """Get recovery events."""
    events = tracker.get_run_events(run_id) if run_id else list(tracker._events.values())
    recovery_types = {
        EventType.RECOVERY_STARTED,
        EventType.RECOVERY_CLASSIFIED,
        EventType.RECOVERY_STRATEGY_SELECTED,
        EventType.RECOVERY_COMPLETED,
        EventType.RECOVERY_EXHAUSTED,
    }
    return [e for e in events if e.event_type in recovery_types]


def get_mcp_events(tracker: CorrelationTracker, run_id: Optional[str] = None) -> List[AgentEvent]:
    """Get MCP events."""
    events = tracker.get_run_events(run_id) if run_id else list(tracker._events.values())
    mcp_types = {
        EventType.MCP_CONNECTED,
        EventType.MCP_DISCONNECTED,
        EventType.MCP_TOOL_REQUESTED,
        EventType.MCP_TOOL_COMPLETED,
        EventType.MCP_TOOL_FAILED,
        EventType.MCP_HEALTH_CHANGED,
    }
    return [e for e in events if e.event_type in mcp_types]


def get_failed_events(tracker: CorrelationTracker, run_id: Optional[str] = None) -> List[AgentEvent]:
    """Get failed events."""
    events = tracker.get_run_events(run_id) if run_id else list(tracker._events.values())
    return [e for e in events if e.is_failure]


def get_capability_events(tracker: CorrelationTracker, capability: str, run_id: Optional[str] = None) -> List[AgentEvent]:
    """Get events for a specific capability."""
    events = tracker.get_run_events(run_id) if run_id else list(tracker._events.values())
    return [e for e in events if e.capability == capability]
