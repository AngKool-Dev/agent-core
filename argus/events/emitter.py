"""Event emitter for ARGUS."""

import time
from typing import Any, Dict, Optional

from argus.events.bus import EventBus, get_event_bus
from argus.events.correlation import CorrelationTracker, get_correlation_tracker
from argus.events.event import AgentEvent, create_event
from argus.events.sinks import EventSink
from argus.events.types import EventSource, EventStatus, EventType


class EventEmitter:
    """Convenience wrapper for emitting events.

    Integrates with EventBus and CorrelationTracker.
    """

    def __init__(self, bus: Optional[EventBus] = None,
                 tracker: Optional[CorrelationTracker] = None,
                 run_id: str = "",
                 session_id: str = ""):
        self._bus = bus or get_event_bus()
        self._tracker = tracker or get_correlation_tracker()
        self._run_id = run_id
        self._session_id = session_id
        self._operation_id: Optional[str] = None
        self._attempt_id: Optional[str] = None

    @property
    def run_id(self) -> str:
        return self._run_id

    @run_id.setter
    def run_id(self, value: str) -> None:
        self._run_id = value

    @property
    def session_id(self) -> str:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._session_id = value

    @property
    def operation_id(self) -> Optional[str]:
        return self._operation_id

    @operation_id.setter
    def operation_id(self, value: Optional[str]) -> None:
        self._operation_id = value

    @property
    def attempt_id(self) -> Optional[str]:
        return self._attempt_id

    @attempt_id.setter
    def attempt_id(self, value: Optional[str]) -> None:
        self._attempt_id = value

    def emit(
        self,
        event_type: EventType,
        source: EventSource,
        status: EventStatus = EventStatus.COMPLETED,
        parent: Optional[AgentEvent] = None,
        capability: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AgentEvent:
        """Emit an event."""
        event = create_event(
            event_type=event_type,
            source=source,
            status=status,
            run_id=self._run_id,
            session_id=self._session_id,
            parent=parent,
            operation_id=self._operation_id,
            attempt_id=self._attempt_id,
            capability=capability,
            metadata=metadata,
            payload=payload,
        )

        self._tracker.track(event)
        self._bus.publish(event)

        return event

    def start_operation(self, operation_id: str) -> None:
        """Set the current operation ID."""
        self._operation_id = operation_id

    def end_operation(self) -> None:
        """Clear the current operation ID."""
        self._operation_id = None

    def start_attempt(self, attempt_id: str) -> None:
        """Set the current attempt ID."""
        self._attempt_id = attempt_id

    def end_attempt(self) -> None:
        """Clear the current attempt ID."""
        self._attempt_id = None

    def timed_emit(
        self,
        event_type: EventType,
        source: EventSource,
        status: EventStatus = EventStatus.COMPLETED,
        capability: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        start_time: Optional[float] = None,
    ) -> AgentEvent:
        """Emit an event with computed duration."""
        duration = None
        if start_time is not None:
            duration = time.time() - start_time

        event = create_event(
            event_type=event_type,
            source=source,
            status=status,
            run_id=self._run_id,
            session_id=self._session_id,
            operation_id=self._operation_id,
            attempt_id=self._attempt_id,
            duration=duration,
            capability=capability,
            metadata=metadata,
        )

        self._tracker.track(event)
        self._bus.publish(event)

        return event


class EventTimedContext:
    """Context manager for timing event emission."""

    def __init__(self, emitter: EventEmitter, event_type: EventType, source: EventSource,
                 capability: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self._emitter = emitter
        self._event_type = event_type
        self._source = source
        self._capability = capability
        self._metadata = metadata
        self._start_time: Optional[float] = None
        self._event: Optional[AgentEvent] = None

    def __enter__(self) -> "EventTimedContext":
        self._start_time = time.time()
        self._event = self._emitter.emit(
            event_type=self._event_type,
            source=self._source,
            status=EventStatus.STARTED,
            capability=self._capability,
            metadata=self._metadata,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        status = EventStatus.FAILED if exc_type else EventStatus.COMPLETED
        duration = time.time() - self._start_time if self._start_time else None

        self._emitter.emit(
            event_type=self._event_type,
            source=self._source,
            status=status,
            capability=self._capability,
            metadata=self._metadata,
        )

    @property
    def event(self) -> Optional[AgentEvent]:
        return self._event

    @property
    def start_time(self) -> Optional[float]:
        return self._start_time
