"""
AgentCore event system.

Provides structured, machine-readable events for observability.

Architecture:
    AgentCore
        |
        v
    EventBus  (optional, no global singleton)
        |
        ├── CLI observer       (future)
        ├── Logger observer    (future)
        ├── DB observer        (future)
        └── Visualizer adapter (future)

Events are synchronous and lightweight. The EventBus can be supplied to
the Agent; if none is provided, AgentCore works normally with no
observable behavior changes.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class EventType(enum.Enum):
    """Types of events emitted by AgentCore."""

    # Task lifecycle
    TASK_STARTED = "task.started"
    TASK_STATE_CHANGED = "task.state_changed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Iterations
    ITERATION_STARTED = "iteration.started"
    ITERATION_COMPLETED = "iteration.completed"

    # Routing / skills
    ROUTE_SELECTED = "route.selected"
    SKILL_DISCOVERED = "skill.discovered"
    SKILL_SELECTED = "skill.selected"
    SKILL_LOADED = "skill.loaded"

    # Planning
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"

    # Runtime / model
    MODEL_REQUEST_STARTED = "model.request.started"
    MODEL_RESPONSE_RECEIVED = "model.response.received"
    MODEL_ERROR = "model.error"

    # Tools
    TOOL_CALL_STARTED = "tool_call.started"
    TOOL_CALL_COMPLETED = "tool_call.completed"
    TOOL_CALL_FAILED = "tool_call.failed"

    # Observations
    OBSERVATION_CREATED = "observation.created"

    # Verification
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_COMPLETED = "verification.completed"

    # Runtime errors
    RUNTIME_ERROR = "runtime.error"

    # Memory
    MEMORY_RECALL_STARTED = "memory.recall.started"
    MEMORY_RECALL_COMPLETED = "memory.recall.completed"
    MEMORY_STORE_STARTED = "memory.store.started"
    MEMORY_STORE_COMPLETED = "memory.store.completed"
    MEMORY_ERROR = "memory.error"
    MEMORY_HARVEST_COMPLETED = "memory.harvest.completed"
    MEMORY_HARVEST_FAILED = "memory.harvest.failed"

    # Persistence & Recovery (Phase 7)
    TASK_CHECKPOINTED = "task.checkpointed"
    TASK_RECOVERED = "task.recovered"
    PERSISTENCE_ERROR = "persistence.error"

    # Lifecycle (Phase 8)
    TASK_REGISTERED = "task.registered"
    TASK_LOCKED = "task.locked"
    TASK_UNLOCKED = "task.unlocked"
    TASK_RESUME_STARTED = "task.resume.started"
    TASK_RESUME_COMPLETED = "task.resume.completed"
    SHUTDOWN_STARTED = "shutdown.started"
    SHUTDOWN_COMPLETED = "shutdown.completed"
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_COMPLETED = "recovery.completed"
    RECOVERY_FAILED = "recovery.failed"


# Type alias for event subscribers
EventHandler = Callable[["AgentEvent"], None]


@dataclass
class AgentEvent:
    """
    A structured event emitted during AgentCore operation.

    All fields are JSON-serializable via to_dict().
    """

    event_type: EventType
    task_id: str = ""
    iteration: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Auto-generated fields
    id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the event to a JSON-serializable dictionary.

        Handles Path, Enum, datetime, dataclasses, and nested structures
        via a simple recursive converter.
        """
        return _serialize_value(
            {
                "id": self.id,
                "timestamp": self.timestamp,
                "event_type": self.event_type.value,
                "task_id": self.task_id,
                "iteration": self.iteration,
                "data": self.data,
                "metadata": self.metadata,
            }
        )


def _serialize_value(value: Any) -> Any:
    """
    Recursively convert a value to JSON-serializable types.

    Handles:
    - Path -> str
    - Enum -> value
    - datetime -> isoformat
    - dataclasses -> asdict-like dict
    - dict -> recursively converted
    - list/tuple -> recursively converted
    - everything else -> returned as-is (assumed JSON-serializable)
    """
    # Path
    if isinstance(value, Path):
        return str(value)

    # Enum
    if isinstance(value, enum.Enum):
        return value.value

    # datetime
    if isinstance(value, datetime):
        return value.isoformat()

    # dataclass
    if _is_dataclass_instance(value):
        result = {}
        for key in value.__dataclass_fields__:
            result[key] = _serialize_value(getattr(value, key))
        return result

    # dict
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}

    # list/tuple
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]

    # Fallback: return as-is
    return value


def _is_dataclass_instance(obj: Any) -> bool:
    """Check if obj is a dataclass instance (not the class itself)."""
    import dataclasses

    return dataclasses.is_dataclass(obj) and not isinstance(obj, type)


class EventBus:
    """
    Lightweight, synchronous event dispatcher.

    No global singleton. Create one and pass it to the Agent:

        bus = EventBus()
        bus.subscribe(my_handler)
        agent = Agent(runtime, memory, event_bus=bus)

    If no EventBus is supplied to the Agent, everything works normally
    with no observable behavior changes.
    """

    def __init__(self) -> None:
        self._subscribers: list[EventHandler] = []

    def subscribe(self, callback: EventHandler) -> None:
        """Register an event handler."""
        if not callable(callback):
            raise TypeError("EventBus.subscribe requires a callable")
        self._subscribers.append(callback)

    def unsubscribe(self, callback: EventHandler) -> None:
        """Remove a registered event handler."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(self, event: AgentEvent) -> None:
        """
        Dispatch an event to all subscribers.

        Subscriber exceptions are caught and logged — they must not
        crash AgentCore.
        """
        if not self._subscribers:
            return

        for subscriber in list(self._subscribers):  # copy for safety
            try:
                subscriber(event)
            except Exception:
                # Subscriber failures must not crash AgentCore
                # Log but continue
                import logging

                logging.getLogger(__name__).exception(
                    "EventBus subscriber raised an exception for event %s",
                    event.event_type.value,
                )

    @property
    def subscriber_count(self) -> int:
        """Number of registered subscribers."""
        return len(self._subscribers)


def create_event(
    event_type: EventType,
    task_id: str = "",
    iteration: int | None = None,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentEvent:
    """Convenience factory for creating events."""
    return AgentEvent(
        event_type=event_type,
        task_id=task_id,
        iteration=iteration,
        data=data or {},
        metadata=metadata or {},
    )
