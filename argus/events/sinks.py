"""Event sinks for ARGUS."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from argus.events.event import AgentEvent

logger = logging.getLogger(__name__)


class EventSink(ABC):
    """Base class for event sinks."""

    @abstractmethod
    def emit(self, event: AgentEvent) -> None:
        """Emit an event to the sink."""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered events."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the sink and release resources."""
        pass


class ConsoleSink(EventSink):
    """Outputs events to console."""

    def __init__(self, formatter: Optional[Callable[[AgentEvent], str]] = None,
                 redact_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None):
        self._formatter = formatter or self._default_formatter
        self._redact_fn = redact_fn

    def emit(self, event: AgentEvent) -> None:
        """Emit event to console."""
        line = self._formatter(event)
        print(line)

    def flush(self) -> None:
        """No-op for console."""
        pass

    def close(self) -> None:
        """No-op for console."""
        pass

    def _default_formatter(self, event: AgentEvent) -> str:
        """Default event formatter."""
        return f"[{event.timestamp:.3f}] {event.event_type.value}: {event.status.value}"


class MemorySink(EventSink):
    """Stores events in memory for later retrieval."""

    def __init__(self, max_events: int = 10000,
                 redact_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None):
        self._events: List[AgentEvent] = []
        self._max_events = max_events
        self._redact_fn = redact_fn

    def emit(self, event: AgentEvent) -> None:
        """Store event in memory."""
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def flush(self) -> None:
        """No-op for memory sink."""
        pass

    def close(self) -> None:
        """Clear stored events."""
        self._events.clear()

    def get_events(self) -> List[AgentEvent]:
        """Get all stored events."""
        return list(self._events)

    def get_events_by_type(self, event_type: str) -> List[AgentEvent]:
        """Get events by type."""
        return [e for e in self._events if e.event_type.value == event_type]

    def get_events_by_run(self, run_id: str) -> List[AgentEvent]:
        """Get events by run ID."""
        return [e for e in self._events if e.run_id == run_id]

    def get_events_by_session(self, session_id: str) -> List[AgentEvent]:
        """Get events by session ID."""
        return [e for e in self._events if e.session_id == session_id]

    def get_events_by_capability(self, capability: str) -> List[AgentEvent]:
        """Get events by capability."""
        return [e for e in self._events if e.capability == capability]

    def clear(self) -> None:
        """Clear all stored events."""
        self._events.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)


class JsonSink(EventSink):
    """Outputs events as JSON strings."""

    def __init__(self, redact_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None):
        self._redact_fn = redact_fn

    def emit(self, event: AgentEvent) -> None:
        """Emit event as JSON."""
        print(event.to_json(redact_fn=self._redact_fn))

    def flush(self) -> None:
        """No-op."""
        pass

    def close(self) -> None:
        """No-op."""
        pass


class AuditTrailSink(EventSink):
    """Integrates with the existing AuditTrail system."""

    def __init__(self, audit_trail=None):
        self._audit_trail = audit_trail

    def emit(self, event: AgentEvent) -> None:
        """Emit event to audit trail if it's a security event."""
        if self._audit_trail is None:
            return

        from argus.security.audit import AuditEventType

        # Map event types to audit event types
        audit_type_map = {
            "security.allowed": AuditEventType.PERMISSION_GRANTED,
            "security.denied": AuditEventType.PERMISSION_DENIED,
            "security.approval_requested": AuditEventType.APPROVAL_REQUESTED,
            "security.approved": AuditEventType.APPROVAL_GRANTED,
            "security.rejected": AuditEventType.APPROVAL_DENIED,
            "security.injection_detected": AuditEventType.INJECTION_DETECTED,
        }

        audit_type = audit_type_map.get(event.event_type.value)
        if audit_type:
            self._audit_trail.record(
                audit_type,
                capability_id=event.capability or "",
                run_id=event.run_id,
                details=event.metadata,
                risk_level=event.metadata.get("risk_level", ""),
                decision=event.status.value,
                reason=event.metadata.get("reason", ""),
            )

    def flush(self) -> None:
        """No-op."""
        pass

    def close(self) -> None:
        """No-op."""
        pass


class CallbackSink(EventSink):
    """Calls a callback function for each event."""

    def __init__(self, callback: Callable[[AgentEvent], None]):
        self._callback = callback

    def emit(self, event: AgentEvent) -> None:
        """Call callback with event."""
        self._callback(event)

    def flush(self) -> None:
        """No-op."""
        pass

    def close(self) -> None:
        """No-op."""
        pass


class MultiSink(EventSink):
    """Sends events to multiple sinks."""

    def __init__(self, *sinks: EventSink):
        self._sinks = list(sinks)

    def add_sink(self, sink: EventSink) -> None:
        """Add a sink."""
        self._sinks.append(sink)

    def remove_sink(self, sink: EventSink) -> None:
        """Remove a sink."""
        self._sinks.remove(sink)

    def emit(self, event: AgentEvent) -> None:
        """Emit event to all sinks."""
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception as e:
                logger.error(f"Sink {sink.__class__.__name__} failed: {e}")

    def flush(self) -> None:
        """Flush all sinks."""
        for sink in self._sinks:
            try:
                sink.flush()
            except Exception as e:
                logger.error(f"Sink {sink.__class__.__name__} flush failed: {e}")

    def close(self) -> None:
        """Close all sinks."""
        for sink in self._sinks:
            try:
                sink.close()
            except Exception as e:
                logger.error(f"Sink {sink.__class__.__name__} close failed: {e}")
