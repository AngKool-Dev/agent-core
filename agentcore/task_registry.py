"""
Task registry and locking for AgentCore Phase 8.

Architecture:
    AgentCore
        |
        v
    TaskRegistry  (orchestration + locking + lifecycle tracking)
        |
        ├── Task records  (in-memory authoritative state)
        └── Task locks    (in-process lock mechanism)

The registry is provider-neutral. Persistence is handled separately
by TaskPersistenceManager.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .task import Task, TaskState, _TERMINAL_STATES
from .persistence import TaskPersistenceManager
from .events import EventBus, EventType, create_event
from .errors import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskLockError,
    TaskRecoveryError,
)

logger = __import__("logging").getLogger(__name__)


class TaskRecordStatus(str, Enum):
    """High-level status of a task in the registry."""
    REGISTERED = "registered"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERED = "recovered"
    RESUME_PENDING = "resume_pending"


@dataclass
class TaskRecord:
    """Registry record for a task."""
    task_id: str
    user_request: str
    project: str
    status: TaskRecordStatus = TaskRecordStatus.REGISTERED
    task_state: TaskState = TaskState.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    locked_by: Optional[str] = None
    lock_acquired_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_request": self.user_request,
            "project": self.project,
            "status": self.status.value if isinstance(self.status, TaskRecordStatus) else self.status,
            "task_state": self.task_state.value if isinstance(self.task_state, TaskState) else self.task_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "locked_by": self.locked_by,
            "lock_acquired_at": self.lock_acquired_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskRecord:
        return cls(
            task_id=data["task_id"],
            user_request=data.get("user_request", ""),
            project=data.get("project", ""),
            status=TaskRecordStatus(data.get("status", TaskRecordStatus.REGISTERED.value)),
            task_state=TaskState(data.get("task_state", TaskState.CREATED.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            locked_by=data.get("locked_by"),
            lock_acquired_at=data.get("lock_acquired_at"),
            metadata=data.get("metadata", {}),
        )


class TaskRegistry:
    """
    Provider-neutral task registry with locking and lifecycle tracking.

    Responsibilities:
    - Track task lifecycle
    - Prevent duplicate execution via locks
    - Support task recovery discovery
    - Emit lifecycle events via EventBus
    - Integrate with persistence for recovery
    """

    def __init__(
        self,
        persistence: Optional[TaskPersistenceManager] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self._tasks: Dict[str, TaskRecord] = {}
        self._locks: Dict[str, str] = {}  # task_id -> lock_holder_id
        self._lock = threading.RLock()
        self._persistence = persistence
        self._event_bus = event_bus

    def set_event_bus(self, event_bus: Optional[EventBus]) -> None:
        self._event_bus = event_bus

    def set_persistence(self, persistence: Optional[TaskPersistenceManager]) -> None:
        self._persistence = persistence

    def _emit(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> None:
        if self._event_bus is None or self._event_bus.subscriber_count == 0:
            return
        try:
            event = create_event(
                event_type=event_type,
                task_id=data.get("task_id", "") if data else "",
                data=data or {},
            )
            self._event_bus.emit(event)
        except Exception:
            logger.debug("Failed to emit registry event", exc_info=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def register(self, task: Task, metadata: Optional[Dict[str, Any]] = None) -> TaskRecord:
        """Register a task in the registry."""
        with self._lock:
            if task.task_id in self._tasks:
                record = self._tasks[task.task_id]
                record.updated_at = self._now()
                record.metadata = metadata or {}
                self._emit(EventType.TASK_STATE_CHANGED, data={
                    "task_id": task.task_id,
                    "current_state": record.task_state.value,
                    "action": "reregistered",
                })
                return record

            record = TaskRecord(
                task_id=task.task_id,
                user_request=task.user_request,
                project=task.project,
                status=TaskRecordStatus.REGISTERED,
                task_state=task.current_state,
                metadata=metadata or {},
            )
            self._tasks[task.task_id] = record
            self._emit(EventType.TASK_REGISTERED, data={
                "task_id": task.task_id,
                "user_request": task.user_request,
                "project": task.project,
            })
            return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        """Get a task record by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> List[TaskRecord]:
        """List all registered tasks."""
        with self._lock:
            return list(self._tasks.values())

    def list_active(self) -> List[TaskRecord]:
        """List tasks that are not in a terminal state."""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.task_state not in _TERMINAL_STATES
            ]

    def list_terminal(self) -> List[TaskRecord]:
        """List tasks in terminal states."""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.task_state in _TERMINAL_STATES
            ]

    def list_resumable(self) -> List[TaskRecord]:
        """List tasks that can be resumed (non-terminal, not locked)."""
        with self._lock:
            return [
                t for t in self._tasks.values()
                if t.task_state not in _TERMINAL_STATES and t.locked_by is None
            ]

    def update_status(self, task_id: str, status: TaskRecordStatus) -> None:
        """Update a task's registry status."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            record.status = status
            record.updated_at = self._now()

    def update_task_state(self, task_id: str, task_state: TaskState) -> None:
        """Update a task's state machine state in the registry."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            record.task_state = task_state
            record.updated_at = self._now()

    def acquire_lock(self, task_id: str, holder_id: str) -> bool:
        """
        Acquire an execution lock for a task.

        Returns True if lock acquired, False if already locked by another holder.
        """
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise TaskNotFoundError(task_id)

            if record.locked_by is not None and record.locked_by != holder_id:
                raise TaskAlreadyRunningError(task_id)

            record.locked_by = holder_id
            record.lock_acquired_at = self._now()
            self._emit(EventType.TASK_LOCKED, data={
                "task_id": task_id,
                "locked_by": holder_id,
            })
            return True

    def release_lock(self, task_id: str, holder_id: str) -> bool:
        """
        Release an execution lock.

        Returns True if lock released, False if not held by this holder.
        Safe to call multiple times.
        """
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return False

            if record.locked_by != holder_id:
                return False

            record.locked_by = None
            record.lock_acquired_at = None
            self._emit(EventType.TASK_UNLOCKED, data={
                "task_id": task_id,
                "released_by": holder_id,
            })
            return True

    def force_release_lock(self, task_id: str) -> bool:
        """Force-release a lock regardless of holder. Used during shutdown."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return False
            if record.locked_by is None:
                return False
            holder = record.locked_by
            record.locked_by = None
            record.lock_acquired_at = None
            self._emit(EventType.TASK_UNLOCKED, data={
                "task_id": task_id,
                "released_by": holder,
                "forced": True,
            })
            return True

    def is_locked(self, task_id: str) -> bool:
        """Check if a task is currently locked."""
        with self._lock:
            record = self._tasks.get(task_id)
            return record.locked_by is not None if record else False

    def remove(self, task_id: str) -> bool:
        """Remove a task from the registry."""
        with self._lock:
            if task_id not in self._tasks:
                return False
            del self._tasks[task_id]
            self._locks.pop(task_id, None)
            return True

    def recover_from_persistence(self, persistence: TaskPersistenceManager) -> List[TaskRecord]:
        """
        Discover and recover incomplete tasks from persistence.

        Returns list of recovered TaskRecord objects.
        """
        recovered = []
        try:
            tasks = persistence.recover_incomplete_tasks()
            for task in tasks:
                with self._lock:
                    record = TaskRecord(
                        task_id=task.task_id,
                        user_request=task.user_request,
                        project=task.project,
                        status=TaskRecordStatus.RECOVERED,
                        task_state=task.current_state,
                        metadata={"recovered": True},
                    )
                    self._tasks[task.task_id] = record
                    recovered.append(record)
                    self._emit(EventType.TASK_RECOVERED, data={
                        "task_id": task.task_id,
                        "current_state": task.current_state.value,
                    })
        except Exception as e:
            logger.warning(f"Recovery failed: {e}")
            self._emit(EventType.RECOVERY_FAILED, data={
                "error": str(e),
            })
        return recovered

    def close(self) -> None:
        """Release all locks and clear registry."""
        with self._lock:
            self._tasks.clear()
            self._locks.clear()
