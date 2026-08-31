"""Event correlation for ARGUS."""

from typing import Any, Dict, List, Optional, Set

from argus.events.event import AgentEvent


class CorrelationTracker:
    """Tracks event correlations for reconstructing execution flows."""

    def __init__(self):
        self._events: Dict[str, AgentEvent] = {}  # event_id -> event
        self._children: Dict[str, List[str]] = {}  # parent_id -> [child_ids]
        self._run_events: Dict[str, List[str]] = {}  # run_id -> [event_ids]
        self._session_events: Dict[str, List[str]] = {}  # session_id -> [event_ids]
        self._operation_events: Dict[str, List[str]] = {}  # operation_id -> [event_ids]
        self._attempt_events: Dict[str, List[str]] = {}  # attempt_id -> [event_ids]
        self._capability_events: Dict[str, List[str]] = {}  # capability_call_id -> [event_ids]

    def track(self, event: AgentEvent) -> None:
        """Track an event for correlation."""
        self._events[event.event_id] = event

        if event.parent_event_id:
            if event.parent_event_id not in self._children:
                self._children[event.parent_event_id] = []
            self._children[event.parent_event_id].append(event.event_id)

        if event.run_id:
            if event.run_id not in self._run_events:
                self._run_events[event.run_id] = []
            self._run_events[event.run_id].append(event.event_id)

        if event.session_id:
            if event.session_id not in self._session_events:
                self._session_events[event.session_id] = []
            self._session_events[event.session_id].append(event.event_id)

        if event.operation_id:
            if event.operation_id not in self._operation_events:
                self._operation_events[event.operation_id] = []
            self._operation_events[event.operation_id].append(event.event_id)

        if event.attempt_id:
            if event.attempt_id not in self._attempt_events:
                self._attempt_events[event.attempt_id] = []
            self._attempt_events[event.attempt_id].append(event.event_id)

        if event.capability_call_id:
            if event.capability_call_id not in self._capability_events:
                self._capability_events[event.capability_call_id] = []
            self._capability_events[event.capability_call_id].append(event.event_id)

    def get_event(self, event_id: str) -> Optional[AgentEvent]:
        """Get an event by ID."""
        return self._events.get(event_id)

    def get_children(self, event_id: str) -> List[AgentEvent]:
        """Get child events of a parent."""
        child_ids = self._children.get(event_id, [])
        return [self._events[eid] for eid in child_ids if eid in self._events]

    def get_run_events(self, run_id: str) -> List[AgentEvent]:
        """Get all events for a run."""
        event_ids = self._run_events.get(run_id, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def get_session_events(self, session_id: str) -> List[AgentEvent]:
        """Get all events for a session."""
        event_ids = self._session_events.get(session_id, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def get_operation_events(self, operation_id: str) -> List[AgentEvent]:
        """Get all events for an operation."""
        event_ids = self._operation_events.get(operation_id, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def get_attempt_events(self, attempt_id: str) -> List[AgentEvent]:
        """Get all events for an attempt."""
        event_ids = self._attempt_events.get(attempt_id, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def get_capability_events(self, capability_call_id: str) -> List[AgentEvent]:
        """Get all events for a capability call."""
        event_ids = self._capability_events.get(capability_call_id, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]

    def get_root_events(self, run_id: str) -> List[AgentEvent]:
        """Get root events (no parent) for a run."""
        events = self.get_run_events(run_id)
        return [e for e in events if e.parent_event_id is None]

    def get_event_tree(self, event_id: str) -> Dict[str, Any]:
        """Get event with all descendants as a tree."""
        event = self._events.get(event_id)
        if not event:
            return {}

        children = self.get_children(event_id)
        return {
            "event": event,
            "children": [self.get_event_tree(c.event_id) for c in children]
        }

    def get_ancestors(self, event_id: str) -> List[AgentEvent]:
        """Get all ancestors of an event."""
        ancestors = []
        event = self._events.get(event_id)
        while event and event.parent_event_id:
            parent = self._events.get(event.parent_event_id)
            if parent:
                ancestors.append(parent)
                event = parent
            else:
                break
        return ancestors

    def get_descendants(self, event_id: str) -> List[AgentEvent]:
        """Get all descendants of an event."""
        descendants = []
        child_ids = self._children.get(event_id, [])
        for child_id in child_ids:
            child = self._events.get(child_id)
            if child:
                descendants.append(child)
                descendants.extend(self.get_descendants(child_id))
        return descendants

    def clear(self) -> None:
        """Clear all tracked events."""
        self._events.clear()
        self._children.clear()
        self._run_events.clear()
        self._session_events.clear()
        self._operation_events.clear()
        self._attempt_events.clear()
        self._capability_events.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def run_count(self) -> int:
        return len(self._run_events)

    @property
    def session_count(self) -> int:
        return len(self._session_events)


# Global correlation tracker
_global_tracker: Optional[CorrelationTracker] = None


def get_correlation_tracker() -> CorrelationTracker:
    """Get the global correlation tracker."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CorrelationTracker()
    return _global_tracker


def reset_correlation_tracker() -> None:
    """Reset the global correlation tracker (for testing)."""
    global _global_tracker
    _global_tracker = None
