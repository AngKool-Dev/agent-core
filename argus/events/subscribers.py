"""Event subscribers for ARGUS."""

import logging
from typing import Any, Callable, Dict, List, Optional

from argus.events.event import AgentEvent
from argus.events.filters import EventFilter, PassthroughFilter

logger = logging.getLogger(__name__)


class EventSubscriber:
    """Base class for event subscribers."""

    def __init__(self, filter_fn: Optional[EventFilter] = None):
        self._filter = filter_fn or PassthroughFilter()

    def matches(self, event: AgentEvent) -> bool:
        """Check if event matches subscriber filter."""
        return self._filter.matches(event)

    def on_event(self, event: AgentEvent) -> None:
        """Handle an event."""
        raise NotImplementedError


class CallbackSubscriber(EventSubscriber):
    """Subscriber that calls a callback function."""

    def __init__(self, callback: Callable[[AgentEvent], None],
                 filter_fn: Optional[EventFilter] = None):
        super().__init__(filter_fn)
        self._callback = callback

    def on_event(self, event: AgentEvent) -> None:
        """Call callback with event."""
        self._callback(event)


class LoggingSubscriber(EventSubscriber):
    """Subscriber that logs events."""

    def __init__(self, filter_fn: Optional[EventFilter] = None,
                 log_level: int = logging.INFO):
        super().__init__(filter_fn)
        self._log_level = log_level

    def on_event(self, event: AgentEvent) -> None:
        """Log event."""
        logger.log(self._log_level, f"Event: {event.event_type.value} [{event.status.value}]")


class CountingSubscriber(EventSubscriber):
    """Subscriber that counts events by type."""

    def __init__(self, filter_fn: Optional[EventFilter] = None):
        super().__init__(filter_fn)
        self._counts: Dict[str, int] = {}

    def on_event(self, event: AgentEvent) -> None:
        """Count event."""
        event_type = event.event_type.value
        self._counts[event_type] = self._counts.get(event_type, 0) + 1

    def get_count(self, event_type: str) -> int:
        """Get count for event type."""
        return self._counts.get(event_type, 0)

    def get_counts(self) -> Dict[str, int]:
        """Get all counts."""
        return dict(self._counts)

    def reset(self) -> None:
        """Reset counts."""
        self._counts.clear()

    @property
    def total_count(self) -> int:
        return sum(self._counts.values())


class CollectingSubscriber(EventSubscriber):
    """Subscriber that collects events."""

    def __init__(self, filter_fn: Optional[EventFilter] = None, max_events: int = 1000):
        super().__init__(filter_fn)
        self._events: List[AgentEvent] = []
        self._max_events = max_events

    def on_event(self, event: AgentEvent) -> None:
        """Collect event."""
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def get_events(self) -> List[AgentEvent]:
        """Get collected events."""
        return list(self._events)

    def clear(self) -> None:
        """Clear collected events."""
        self._events.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)


class AlertSubscriber(EventSubscriber):
    """Subscriber that triggers alerts on specific events."""

    def __init__(self, alert_fn: Callable[[AgentEvent], None],
                 filter_fn: Optional[EventFilter] = None):
        super().__init__(filter_fn)
        self._alert_fn = alert_fn

    def on_event(self, event: AgentEvent) -> None:
        """Trigger alert if event matches."""
        try:
            self._alert_fn(event)
        except Exception as e:
            logger.error(f"Alert failed for event {event.event_id}: {e}")
