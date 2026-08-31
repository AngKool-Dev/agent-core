"""Event filtering for ARGUS."""

from typing import Any, Callable, List, Optional, Set

from argus.events.event import AgentEvent
from argus.events.types import EventSource, EventStatus, EventType


class EventFilter:
    """Base class for event filters."""

    def matches(self, event: AgentEvent) -> bool:
        """Check if event matches filter."""
        raise NotImplementedError


class PassthroughFilter(EventFilter):
    """Matches all events."""

    def matches(self, event: AgentEvent) -> bool:
        return True


class EventTypeFilter(EventFilter):
    """Filter by event types."""

    def __init__(self, event_types: List[EventType]):
        self._event_types: Set[EventType] = set(event_types)

    def matches(self, event: AgentEvent) -> bool:
        return event.event_type in self._event_types


class EventSourceFilter(EventFilter):
    """Filter by event sources."""

    def __init__(self, sources: List[EventSource]):
        self._sources: Set[EventSource] = set(sources)

    def matches(self, event: AgentEvent) -> bool:
        return event.source in self._sources


class EventStatusFilter(EventFilter):
    """Filter by event status."""

    def __init__(self, statuses: List[EventStatus]):
        self._statuses: Set[EventStatus] = set(statuses)

    def matches(self, event: AgentEvent) -> bool:
        return event.status in self._statuses


class CapabilityFilter(EventFilter):
    """Filter by capability."""

    def __init__(self, capabilities: List[str]):
        self._capabilities: Set[str] = set(capabilities)

    def matches(self, event: AgentEvent) -> bool:
        return event.capability in self._capabilities if event.capability else False


class RunFilter(EventFilter):
    """Filter by run ID."""

    def __init__(self, run_ids: List[str]):
        self._run_ids: Set[str] = set(run_ids)

    def matches(self, event: AgentEvent) -> bool:
        return event.run_id in self._run_ids


class SessionFilter(EventFilter):
    """Filter by session ID."""

    def __init__(self, session_ids: List[str]):
        self._session_ids: Set[str] = set(session_ids)

    def matches(self, event: AgentEvent) -> bool:
        return event.session_id in self._session_ids


class TimeRangeFilter(EventFilter):
    """Filter by time range."""

    def __init__(self, start: Optional[float] = None, end: Optional[float] = None):
        self._start = start
        self._end = end

    def matches(self, event: AgentEvent) -> bool:
        if self._start is not None and event.timestamp < self._start:
            return False
        if self._end is not None and event.timestamp > self._end:
            return False
        return True


class SuccessFilter(EventFilter):
    """Filter for successful events."""

    def matches(self, event: AgentEvent) -> bool:
        return event.is_success


class FailureFilter(EventFilter):
    """Filter for failure events."""

    def matches(self, event: AgentEvent) -> bool:
        return event.is_failure


class SecurityFilter(EventFilter):
    """Filter for security events."""

    def __init__(self):
        self._types = {
            EventType.SECURITY_ALLOWED,
            EventType.SECURITY_DENIED,
            EventType.SECURITY_APPROVAL_REQUESTED,
            EventType.SECURITY_APPROVED,
            EventType.SECURITY_REJECTED,
            EventType.SECURITY_INJECTION_DETECTED,
        }

    def matches(self, event: AgentEvent) -> bool:
        return event.event_type in self._types


class RecoveryFilter(EventFilter):
    """Filter for recovery events."""

    def __init__(self):
        self._types = {
            EventType.RECOVERY_STARTED,
            EventType.RECOVERY_CLASSIFIED,
            EventType.RECOVERY_STRATEGY_SELECTED,
            EventType.RECOVERY_COMPLETED,
            EventType.RECOVERY_EXHAUSTED,
        }

    def matches(self, event: AgentEvent) -> bool:
        return event.event_type in self._types


class MCPFilter(EventFilter):
    """Filter for MCP events."""

    def __init__(self):
        self._types = {
            EventType.MCP_CONNECTED,
            EventType.MCP_DISCONNECTED,
            EventType.MCP_TOOL_REQUESTED,
            EventType.MCP_TOOL_COMPLETED,
            EventType.MCP_TOOL_FAILED,
            EventType.MCP_HEALTH_CHANGED,
        }

    def matches(self, event: AgentEvent) -> bool:
        return event.event_type in self._types


class AndFilter(EventFilter):
    """Combine filters with AND logic."""

    def __init__(self, *filters: EventFilter):
        self._filters = filters

    def matches(self, event: AgentEvent) -> bool:
        return all(f.matches(event) for f in self._filters)


class OrFilter(EventFilter):
    """Combine filters with OR logic."""

    def __init__(self, *filters: EventFilter):
        self._filters = filters

    def matches(self, event: AgentEvent) -> bool:
        return any(f.matches(event) for f in self._filters)


class NotFilter(EventFilter):
    """Negate a filter."""

    def __init__(self, filter_fn: EventFilter):
        self._filter = filter_fn

    def matches(self, event: AgentEvent) -> bool:
        return not self._filter.matches(event)


class CustomFilter(EventFilter):
    """Filter using a custom function."""

    def __init__(self, fn: Callable[[AgentEvent], bool]):
        self._fn = fn

    def matches(self, event: AgentEvent) -> bool:
        return self._fn(event)
