"""
Observation model — structured execution records for Argus.

Architecture
------------
    HermesEventBridge
        ↓
    Argus EventBus
        ↓
    ObservationCollector
        ↓
    Observation
        ↓
    ObservationStore  (abstraction)
        ↓
    [future: DB-Obsidian, CLI, visualizer, ...]

An Observation is a structured record of something that happened during
an execution.  It is NOT the same as an EventBus event:

* Events are transient signals.
* Observations are durable, queryable records.
* Memories are curated knowledge extracted from observations.

Observations carry stable correlation identifiers so that downstream
consumers can reconstruct execution structure without re-parsing raw
event streams.
"""

from __future__ import annotations

import enum
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class ObservationType(enum.StrEnum):
    """Types of execution observations."""

    TASK_REGISTERED = "task.registered"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_STATE_CHANGED = "task.state_changed"

    MODEL_REQUEST_STARTED = "model.request.started"
    MODEL_RESPONSE_RECEIVED = "model.response.received"
    MODEL_ERROR = "model.error"

    TOOL_CALL_STARTED = "tool_call.started"
    TOOL_CALL_COMPLETED = "tool_call.completed"
    TOOL_CALL_FAILED = "tool_call.failed"

    RUNTIME_ERROR = "runtime.error"
    OBSERVATION_CREATED = "observation.created"


@dataclass
class Observation:
    """A structured execution observation."""

    id: str = field(default_factory=lambda: f"obs-{uuid.uuid4().hex[:12]}")
    task_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    event_id: str = ""
    tool_call_id: str = ""
    model_request_id: str = ""
    observation_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "event_id": self.event_id,
            "tool_call_id": self.tool_call_id,
            "model_request_id": self.model_request_id,
            "observation_type": self.observation_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Observation:
        return cls(
            id=data.get("id", f"obs-{uuid.uuid4().hex[:12]}"),
            task_id=data.get("task_id", ""),
            session_id=data.get("session_id", ""),
            turn_id=data.get("turn_id", ""),
            event_id=data.get("event_id", ""),
            tool_call_id=data.get("tool_call_id", ""),
            model_request_id=data.get("model_request_id", ""),
            observation_type=data.get("observation_type", ""),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            sequence=data.get("sequence", 0),
        )


class ObservationStore:
    """Backend-agnostic observation storage abstraction."""

    def add(self, observation: Observation) -> None:
        raise NotImplementedError

    def get(self, observation_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def list_by_task(self, task_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_by_session(self, session_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        raise NotImplementedError

    def clear(self, task_id: str) -> int:
        raise NotImplementedError


class InMemoryObservationStore(ObservationStore):
    """In-memory observation store for testing and default usage."""

    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}
        self._by_task: dict[str, list[str]] = {}
        self._by_session: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def add(self, observation: Observation) -> None:
        with self._lock:
            self._observations[observation.id] = observation
            self._by_task.setdefault(observation.task_id, []).append(observation.id)
            self._by_session.setdefault(observation.session_id, []).append(observation.id)

    def get(self, observation_id: str) -> Observation | None:
        with self._lock:
            obs = self._observations.get(observation_id)
            return obs.to_dict() if obs else None

    def list_by_task(self, task_id: str, limit: int = 1000) -> list[Observation]:
        with self._lock:
            ids = self._by_task.get(task_id, [])[-limit:]
            return [self._observations[oid].to_dict() for oid in ids if oid in self._observations]

    def list_by_session(self, session_id: str, limit: int = 1000) -> list[Observation]:
        with self._lock:
            ids = self._by_session.get(session_id, [])[-limit:]
            return [self._observations[oid].to_dict() for oid in ids if oid in self._observations]

    def clear(self, task_id: str) -> int:
        with self._lock:
            ids = self._by_task.pop(task_id, [])
            for oid in ids:
                obs = self._observations.pop(oid, None)
                if obs:
                    self._by_session.get(obs.session_id, []).remove(oid)
            return len(ids)


class ObservationCollector:
    """
    Consumes Argus EventBus events and produces structured Observations.

    The collector subscribes to the EventBus and translates events into
    Observations with stable correlation identifiers.  It does NOT replace
    the EventBus — it observes it.

    Correlation
    -----------
    * task_id       — from event metadata or event data
    * session_id    — from event metadata
    * turn_id       — from event metadata
    * tool_call_id  — from event metadata or payload
    * model_request_id — generated per MODEL_REQUEST_STARTED
    * event_id      — from the EventBus event itself

    Sequence numbers are assigned per observation stream so that ordering
    can be reconstructed without relying on timestamps alone.
    """

    def __init__(self, store: ObservationStore | None = None) -> None:
        self._store = store or InMemoryObservationStore()
        self._lock = threading.Lock()
        self._sequence = 0
        self._subscribed = False
        self._active_model_requests: dict[str, str] = {}

    def start(self) -> None:
        """Start observing events. Safe to call multiple times."""
        if self._subscribed:
            return
        self._subscribed = True

    def stop(self) -> None:
        """Stop observing events."""
        self._subscribed = False

    def handle_event(self, event: Any) -> dict[str, Any] | None:
        """Process a single EventBus event and return the observation dict."""
        if not self._subscribed:
            return None
        try:
            observation = self._handle_event_inner(event)
            return observation.to_dict() if observation else None
        except Exception:
            return None

    def _handle_event_inner(self, event: Any) -> Observation | None:
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return None

        metadata = getattr(event, "metadata", {}) or {}
        data = getattr(event, "data", {}) or {}
        event_id = getattr(event, "id", "")

        session_id = str(metadata.get("session_id") or data.get("session_id") or "")
        task_id = str(metadata.get("task_id") or data.get("task_id") or session_id)
        turn_id = str(metadata.get("turn_id") or data.get("turn_id") or "")
        tool_call_id = str(
            metadata.get("tool_id")
            or metadata.get("tool_call_id")
            or data.get("tool_id")
            or data.get("tool_call_id")
            or ""
        )
        model_request_id = self._resolve_model_request_id(event_type, metadata, data)

        obs_type = self._map_event_type(event_type)
        if obs_type is None:
            return None

        with self._lock:
            self._sequence += 1
            sequence = self._sequence

        observation = Observation(
            task_id=task_id,
            session_id=session_id,
            turn_id=turn_id,
            event_id=event_id,
            tool_call_id=tool_call_id,
            model_request_id=model_request_id,
            observation_type=obs_type,
            payload=dict(data) if data else {},
            metadata=dict(metadata) if metadata else {},
            sequence=sequence,
        )

        self._store.add(observation)
        return observation

    def _resolve_model_request_id(
        self, event_type: Any, metadata: dict[str, Any], data: dict[str, Any]
    ) -> str:
        """Get or create a model request correlation ID."""
        if event_type.value in ("model.request.started",):
            request_id = str(
                metadata.get("model_request_id")
                or data.get("model_request_id")
                or f"req-{uuid.uuid4().hex[:8]}"
            )
            with self._lock:
                self._active_model_requests[request_id] = request_id
            return request_id
        if event_type.value in ("model.response.received", "model.error"):
            return self._active_model_requests.get(
                str(metadata.get("model_request_id") or data.get("model_request_id") or ""), ""
            )
        return ""

    def _map_event_type(self, event_type: Any) -> str | None:
        """Map EventType to observation type string."""
        mapping = {
            "task.registered": ObservationType.TASK_REGISTERED.value,
            "task.started": ObservationType.TASK_STARTED.value,
            "task.completed": ObservationType.TASK_COMPLETED.value,
            "task.failed": ObservationType.TASK_FAILED.value,
            "task.cancelled": ObservationType.TASK_CANCELLED.value,
            "task.state_changed": ObservationType.TASK_STATE_CHANGED.value,
            "model.request.started": ObservationType.MODEL_REQUEST_STARTED.value,
            "model.response.received": ObservationType.MODEL_RESPONSE_RECEIVED.value,
            "model.error": ObservationType.MODEL_ERROR.value,
            "tool_call.started": ObservationType.TOOL_CALL_STARTED.value,
            "tool_call.completed": ObservationType.TOOL_CALL_COMPLETED.value,
            "tool_call.failed": ObservationType.TOOL_CALL_FAILED.value,
            "runtime.error": ObservationType.RUNTIME_ERROR.value,
            "observation.created": ObservationType.OBSERVATION_CREATED.value,
        }
        key = event_type.value if hasattr(event_type, "value") else str(event_type)
        return mapping.get(key)

    def get_observations(self, task_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        """List observations for a task."""
        return self._store.list_by_task(task_id, limit)

    def get_store(self) -> ObservationStore:
        """Return the underlying observation store."""
        return self._store
