"""ARGUS Replay execution tree - reconstructs parent/child relationships."""

from typing import Any, Dict, List, Optional

from argus.replay.models import (
    ExecutionNode,
    ReplayEvent,
    ReplayRun,
)


def build_execution_tree(run: ReplayRun) -> Optional[ExecutionNode]:
    """Build the execution tree for a run.

    Reconstructs parent/child relationships from event correlation data.

    Args:
        run: The replay run

    Returns:
        Root execution node, or None if no events
    """
    if not run.events:
        return None

    # Sort events by sequence
    events = sorted(run.events, key=lambda e: (e.sequence, e.timestamp, e.event_id))

    # Create nodes
    nodes: Dict[str, ExecutionNode] = {}
    root = ExecutionNode(
        node_id="root",
        event_type="run",
        category="run",
        source="agent",
        timestamp=events[0].timestamp,
        sequence=-1,
    )

    # Track parent-child relationships
    active_stack: List[ExecutionNode] = [root]

    for event in events:
        node = ExecutionNode(
            node_id=event.event_id,
            event_type=event.event_type,
            category=event.category,
            source=event.source,
            timestamp=event.timestamp,
            status=event.status,
            capability=event.capability,
            sequence=event.sequence,
        )
        nodes[event.event_id] = node

        # Find parent based on operation_id/attempt_id or parent_id
        parent = _find_parent(event, active_stack, nodes, root)
        node.parent_id = parent.node_id
        parent.children.append(node)

        # Manage stack based on event type
        if _is_start_event(event):
            active_stack.append(node)
        elif _is_end_event(event) and len(active_stack) > 1:
            active_stack.pop()

    return root


def _find_parent(
    event: ReplayEvent,
    active_stack: List[ExecutionNode],
    nodes: Dict[str, ExecutionNode],
    root: ExecutionNode,
) -> ExecutionNode:
    """Find the parent node for an event."""
    # First check parent_id
    if event.parent_id and event.parent_id in nodes:
        return nodes[event.parent_id]

    # Check operation_id for grouping
    if event.operation_id:
        for node_id, node in nodes.items():
            if node.node_id != event.event_id:
                # Same operation_id means same parent context
                pass

    # Use the active stack
    if len(active_stack) > 1:
        return active_stack[-1]

    return root


def _is_start_event(event: ReplayEvent) -> bool:
    """Check if an event is a start event."""
    start_types = {
        "agent.started",
        "capability.started",
        "execution.started",
        "recovery.started",
        "verification.started",
        "step.started",
        "mcp.connected",
        "subagent.created",
    }
    return event.event_type in start_types


def _is_end_event(event: ReplayEvent) -> bool:
    """Check if an event is an end event."""
    end_types = {
        "agent.completed",
        "agent.failed",
        "agent.paused",
        "capability.completed",
        "capability.failed",
        "execution.completed",
        "execution.failed",
        "recovery.completed",
        "recovery.exhausted",
        "verification.completed",
        "verification.failed",
        "step.completed",
        "mcp.disconnected",
        "subagent.completed",
        "subagent.failed",
    }
    return event.event_type in end_types


def format_execution_tree(node: ExecutionNode, indent: int = 0) -> str:
    """Format an execution tree as a string."""
    prefix = "  " * indent
    line = f"{prefix}├── {node.event_type}"
    if node.capability:
        line += f" ({node.capability})"
    if node.status:
        line += f" [{node.status}]"

    lines = [line]
    for child in node.children:
        lines.append(format_execution_tree(child, indent + 1))

    return "\n".join(lines)
