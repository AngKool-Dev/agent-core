"""UX event handling and subscription."""

import threading
from typing import Callable, List, Optional

from argus.events import AgentEvent, EventBus, get_event_bus
from argus.ux.models import EventSeverity, UIEvent


class UXEventSubscriber:
    """Subscribes to EventBus and converts events to UI events."""

    def __init__(self, bus: Optional[EventBus] = None):
        self._bus = bus or get_event_bus()
        self._handlers: List[Callable[[UIEvent], None]] = []
        self._lock = threading.Lock()
        self._active = False

    def start(self) -> None:
        """Start subscribing to events."""
        with self._lock:
            if self._active:
                return
            self._bus.subscribe(self._on_agent_event)
            self._bus.subscribe(self._on_tool_event)
            self._bus.subscribe(self._on_security_event)
            self._bus.subscribe(self._on_performance_event)
            self._active = True

    def stop(self) -> None:
        """Stop subscribing to events."""
        with self._lock:
            if not self._active:
                return
            self._bus.unsubscribe(self._on_agent_event)
            self._bus.unsubscribe(self._on_tool_event)
            self._bus.unsubscribe(self._on_security_event)
            self._bus.unsubscribe(self._on_performance_event)
            self._active = False

    def add_handler(self, handler: Callable[[UIEvent], None]) -> None:
        """Add a handler for UI events."""
        with self._lock:
            self._handlers.append(handler)

    def remove_handler(self, handler: Callable[[UIEvent], None]) -> None:
        """Remove a handler."""
        with self._lock:
            self._handlers.remove(handler)

    def _on_agent_event(self, event: AgentEvent) -> None:
        """Handle agent events."""
        ui_event = UIEvent(
            event_id=getattr(event, "event_id", ""),
            event_type="agent",
            severity=EventSeverity.INFO,
            message=getattr(event, "message", str(event)),
            run_id=getattr(event, "run_id", None),
            metadata=getattr(event, "metadata", {}),
        )
        self._notify_handlers(ui_event)

    def _on_tool_event(self, event: AgentEvent) -> None:
        """Handle tool events."""
        ui_event = UIEvent(
            event_id=getattr(event, "event_id", ""),
            event_type="tool",
            severity=EventSeverity.INFO,
            message=getattr(event, "message", str(event)),
            run_id=getattr(event, "run_id", None),
            capability_id=getattr(event, "capability_id", None),
            metadata=getattr(event, "metadata", {}),
        )
        self._notify_handlers(ui_event)

    def _on_security_event(self, event: AgentEvent) -> None:
        """Handle security events."""
        ui_event = UIEvent(
            event_id=getattr(event, "event_id", ""),
            event_type="security",
            severity=EventSeverity.WARNING,
            message=getattr(event, "message", str(event)),
            run_id=getattr(event, "run_id", None),
            metadata=getattr(event, "metadata", {}),
        )
        self._notify_handlers(ui_event)

    def _on_performance_event(self, event: AgentEvent) -> None:
        """Handle performance events."""
        ui_event = UIEvent(
            event_id=getattr(event, "event_id", ""),
            event_type="performance",
            severity=EventSeverity.DEBUG,
            message=getattr(event, "message", str(event)),
            run_id=getattr(event, "run_id", None),
            metadata=getattr(event, "metadata", {}),
        )
        self._notify_handlers(ui_event)

    def _notify_handlers(self, event: UIEvent) -> None:
        """Notify all handlers of a UI event."""
        with self._lock:
            handlers = list(self._handlers)
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors break the subscriber

    @property
    def is_active(self) -> bool:
        """Check if subscriber is active."""
        return self._active
