"""Canonical AgentEvent for ARGUS."""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

from argus.events.types import EventSource, EventStatus, EventType, get_category


def _generate_event_id() -> str:
    """Generate a unique event ID."""
    return str(uuid.uuid4())[:12]


def _current_timestamp() -> float:
    """Get current timestamp."""
    return time.time()


@dataclass(frozen=True)
class AgentEvent:
    """Canonical event for ARGUS observability.

    Events are immutable after creation.
    All timestamps are timezone-aware (UTC).
    """
    event_type: EventType
    source: EventSource
    status: EventStatus = EventStatus.COMPLETED

    # Identifiers
    event_id: str = field(default_factory=_generate_event_id)
    run_id: str = ""
    session_id: str = ""
    parent_event_id: Optional[str] = None
    operation_id: Optional[str] = None
    attempt_id: Optional[str] = None
    capability_call_id: Optional[str] = None

    # Timing
    timestamp: float = field(default_factory=_current_timestamp)
    duration: Optional[float] = None

    # Content
    capability: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate event after creation."""
        if not isinstance(self.event_type, EventType):
            object.__setattr__(self, 'event_type', EventType(self.event_type))
        if not isinstance(self.source, EventSource):
            object.__setattr__(self, 'source', EventSource(self.source))
        if not isinstance(self.status, EventStatus):
            object.__setattr__(self, 'status', EventStatus(self.status))

    @property
    def category(self) -> str:
        """Get event category."""
        return get_category(self.event_type)

    @property
    def is_success(self) -> bool:
        """Check if event represents success."""
        return self.status in (
            EventStatus.COMPLETED,
            EventStatus.ALLOWED,
            EventStatus.GRANTED,
        )

    @property
    def is_failure(self) -> bool:
        """Check if event represents failure."""
        return self.status in (
            EventStatus.FAILED,
            EventStatus.DENIED,
            EventStatus.REJECTED,
            EventStatus.EXHAUSTED,
        )

    def to_dict(self, redact_fn=None) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "parent_event_id": self.parent_event_id,
            "operation_id": self.operation_id,
            "attempt_id": self.attempt_id,
            "capability_call_id": self.capability_call_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "status": self.status.value,
            "category": self.category,
            "duration": self.duration,
            "capability": self.capability,
            "metadata": dict(self.metadata),
            "payload": dict(self.payload),
        }

        if redact_fn:
            data = redact_fn(data)

        return data

    def to_json(self, redact_fn=None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(redact_fn=redact_fn), default=str)

    def fingerprint(self) -> str:
        """Generate a deterministic fingerprint for deduplication."""
        content = f"{self.event_type.value}:{self.run_id}:{self.timestamp}:{self.status.value}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def with_parent(self, parent: "AgentEvent") -> "AgentEvent":
        """Create a child event with parent reference."""
        return AgentEvent(
            event_type=self.event_type,
            source=self.source,
            status=self.status,
            run_id=self.run_id or parent.run_id,
            session_id=self.session_id or parent.session_id,
            parent_event_id=parent.event_id,
            operation_id=self.operation_id or parent.operation_id,
            attempt_id=self.attempt_id,
            capability_call_id=self.capability_call_id,
            duration=self.duration,
            capability=self.capability,
            metadata=dict(self.metadata),
            payload=dict(self.payload),
        )

    def with_status(self, status: EventStatus) -> "AgentEvent":
        """Create a copy with different status."""
        return AgentEvent(
            event_type=self.event_type,
            source=self.source,
            status=status,
            run_id=self.run_id,
            session_id=self.session_id,
            parent_event_id=self.parent_event_id,
            operation_id=self.operation_id,
            attempt_id=self.attempt_id,
            capability_call_id=self.capability_call_id,
            duration=self.duration,
            capability=self.capability,
            metadata=dict(self.metadata),
            payload=dict(self.payload),
        )

    def with_duration(self, duration: float) -> "AgentEvent":
        """Create a copy with duration."""
        return AgentEvent(
            event_type=self.event_type,
            source=self.source,
            status=self.status,
            run_id=self.run_id,
            session_id=self.session_id,
            parent_event_id=self.parent_event_id,
            operation_id=self.operation_id,
            attempt_id=self.attempt_id,
            capability_call_id=self.capability_call_id,
            duration=duration,
            capability=self.capability,
            metadata=dict(self.metadata),
            payload=dict(self.payload),
        )


def create_event(
    event_type: EventType,
    source: EventSource,
    status: EventStatus = EventStatus.COMPLETED,
    run_id: str = "",
    session_id: str = "",
    parent: Optional[AgentEvent] = None,
    operation_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    capability_call_id: Optional[str] = None,
    duration: Optional[float] = None,
    capability: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AgentEvent:
    """Factory function to create an AgentEvent."""
    # Inherit run_id and session_id from parent if not explicitly provided
    if parent:
        run_id = run_id or parent.run_id
        session_id = session_id or parent.session_id

    return AgentEvent(
        event_type=event_type,
        source=source,
        status=status,
        run_id=run_id,
        session_id=session_id,
        parent_event_id=parent.event_id if parent else None,
        operation_id=operation_id or (parent.operation_id if parent else None),
        attempt_id=attempt_id,
        capability_call_id=capability_call_id,
        duration=duration,
        capability=capability,
        metadata=metadata or {},
        payload=payload or {},
    )
