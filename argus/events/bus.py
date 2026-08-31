"""EventBus for ARGUS."""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from argus.events.event import AgentEvent
from argus.events.filters import EventFilter, PassthroughFilter

logger = logging.getLogger(__name__)

# Type alias for subscriber callback
SubscriberCallback = Callable[[AgentEvent], None]


class EventBus:
    """Lightweight event bus for ARGUS.

    Supports multiple subscribers, event filtering, and subscriber isolation.
    Subscriber failures do not crash the bus or agent.
    """

    def __init__(self):
        self._subscribers: Dict[str, tuple] = {}  # id -> (callback, filter)
        self._lock = threading.Lock()
        self._active = True
        self._event_count = 0
        self._error_count = 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def error_count(self) -> int:
        return self._error_count

    def publish(self, event: AgentEvent) -> int:
        """Publish an event to all matching subscribers.

        Returns the number of subscribers notified.
        """
        if not self._active:
            return 0

        self._event_count += 1
        notified = 0

        with self._lock:
            subscribers = list(self._subscribers.items())

        for sub_id, (callback, filter_fn) in subscribers:
            try:
                if filter_fn.matches(event):
                    callback(event)
                    notified += 1
            except Exception as e:
                self._error_count += 1
                logger.error(f"Subscriber {sub_id} failed: {e}")

        return notified

    def subscribe(
        self,
        callback: SubscriberCallback,
        filter_fn: Optional[EventFilter] = None,
        subscriber_id: Optional[str] = None,
    ) -> str:
        """Subscribe to events.

        Returns a subscriber ID for later unsubscribe.
        """
        if subscriber_id is None:
            subscriber_id = f"sub_{len(self._subscribers)}_{id(callback)}"

        with self._lock:
            self._subscribers[subscriber_id] = (callback, filter_fn or PassthroughFilter())

        return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Unsubscribe from events."""
        with self._lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                return True
        return False

    def clear_subscribers(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()

    def shutdown(self) -> None:
        """Shutdown the event bus."""
        self._active = False
        self.clear_subscribers()

    def get_subscriber_ids(self) -> List[str]:
        """Get all subscriber IDs."""
        with self._lock:
            return list(self._subscribers.keys())


# Global event bus instance
_global_bus: Optional[EventBus] = None
_global_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_bus
    if _global_bus is None:
        with _global_bus_lock:
            if _global_bus is None:
                _global_bus = EventBus()
    return _global_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _global_bus
    with _global_bus_lock:
        if _global_bus is not None:
            _global_bus.shutdown()
        _global_bus = None
