"""
AgentCore persistence & recovery architecture (Phase 7).

Architecture:
    AgentCore
        |
        v
    TaskPersistenceManager  (orchestration + failure isolation + security filtering)
        |
        ├── PersistenceBackend  (abstract provider interface)
        │   ├── InMemoryPersistenceBackend  (test/default)
        │   └── FilesystemPersistenceBackend  (atomic filesystem persistence)
        |
        └── EventStore  (abstract event interface)
            ├── InMemoryEventStore  (test/default)
            └── FilesystemEventStore  (persistent event log)

Persistence is optional. If the backend fails, AgentCore logs and continues.
"""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import uuid

from .config import user_data_dir
from .events import AgentEvent, EventType, EventBus, create_event
from .task import Task, TaskState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Security filtering
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS = [
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "private_key",
    "credential",
]


def _contains_sensitive_data(text: str) -> bool:
    """Conservative check for potentially sensitive content."""
    lower = text.lower()
    return any(pattern in lower for pattern in _SENSITIVE_PATTERNS)


def _sanitize_for_persistence(data: Any, max_output_length: int = 2000) -> Any:
    """Sanitize data before persistence: filter sensitive data and bound output."""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, Path):
                sanitized[key] = str(value)
            elif isinstance(value, str):
                if _contains_sensitive_data(value):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = value[:max_output_length]
            elif isinstance(value, dict):
                sanitized[key] = _sanitize_for_persistence(value, max_output_length)
            elif isinstance(value, list):
                sanitized_list = []
                for item in value[:100]:
                    if isinstance(item, dict):
                        sanitized_list.append(_sanitize_for_persistence(item, max_output_length))
                    elif isinstance(item, str):
                        if _contains_sensitive_data(item):
                            sanitized_list.append("[REDACTED]")
                        else:
                            sanitized_list.append(item[:max_output_length])
                    else:
                        sanitized_list.append(item)
                sanitized[key] = sanitized_list
            else:
                sanitized[key] = value
        return sanitized
    elif isinstance(data, list):
        sanitized_list = []
        for item in data[:100]:
            if isinstance(item, dict):
                sanitized_list.append(_sanitize_for_persistence(item, max_output_length))
            elif isinstance(item, str):
                if _contains_sensitive_data(item):
                    sanitized_list.append("[REDACTED]")
                else:
                    sanitized_list.append(item[:max_output_length])
            else:
                sanitized_list.append(item)
        return sanitized_list
    elif isinstance(data, str):
        if _contains_sensitive_data(data):
            return "[REDACTED]"
        return data[:max_output_length]
    return data


# ---------------------------------------------------------------------------
# PersistenceBackend interface
# ---------------------------------------------------------------------------

class PersistenceBackend(ABC):
    """Provider-neutral interface for task record persistence."""

    @abstractmethod
    def save_task(self, task_id: str, task_dict: Dict[str, Any], schema_version: int = CURRENT_SCHEMA_VERSION) -> bool:
        """Save a task record. Returns True on success."""
        pass

    @abstractmethod
    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load a task record by ID. Returns None if not found."""
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """Delete a task record. Returns True if deleted."""
        pass

    @abstractmethod
    def list_tasks(self) -> List[str]:
        """List all task IDs."""
        pass

    @abstractmethod
    def save_event(self, event_dict: Dict[str, Any]) -> bool:
        """Append an event to the persistent log. Returns True on success."""
        pass

    @abstractmethod
    def get_events(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events for a task, newest first."""
        pass

    @abstractmethod
    def clear(self, task_id: Optional[str] = None) -> int:
        """Clear all data, or data for a specific task. Returns count cleared."""
        pass


# ---------------------------------------------------------------------------
# InMemoryPersistenceBackend
# ---------------------------------------------------------------------------

class InMemoryPersistenceBackend(PersistenceBackend):
    """In-memory persistence backend for testing and development.

    No external dependencies. Not persistent across process restarts.
    """

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def save_task(self, task_id: str, task_dict: Dict[str, Any], schema_version: int = CURRENT_SCHEMA_VERSION) -> bool:
        record = dict(task_dict)
        record["schema_version"] = schema_version
        record["_persisted_at"] = datetime.now(timezone.utc).isoformat()
        self._tasks[task_id] = record
        return True

    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    def delete_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def list_tasks(self) -> List[str]:
        return list(self._tasks.keys())

    def save_event(self, event_dict: Dict[str, Any]) -> bool:
        task_id = event_dict.get("task_id", "")
        if task_id not in self._events:
            self._events[task_id] = []
        self._events[task_id].append(dict(event_dict))
        return True

    def get_events(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        events = self._events.get(task_id, [])
        return events[-limit:]

    def clear(self, task_id: Optional[str] = None) -> int:
        if task_id is None:
            count = len(self._tasks) + sum(len(v) for v in self._events.values())
            self._tasks.clear()
            self._events.clear()
            return count
        count = 0
        if task_id in self._tasks:
            del self._tasks[task_id]
            count += 1
        if task_id in self._events:
            count += len(self._events[task_id])
            del self._events[task_id]
        return count

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# FilesystemPersistenceBackend
# ---------------------------------------------------------------------------

class FilesystemPersistenceBackend(PersistenceBackend):
    """Crash-safe atomic filesystem persistence backend.

    Writes are performed atomically: data is written to a temporary file
    first, then moved into place with os.replace().
    """

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            base_path = user_data_dir() / "tasks"
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._tasks_dir = self._base_path / "tasks"
        self._events_dir = self._base_path / "events"
        self._tasks_dir.mkdir(exist_ok=True)
        self._events_dir.mkdir(exist_ok=True)

    def _task_path(self, task_id: str) -> Path:
        return self._tasks_dir / f"{task_id}.json"

    def _event_path(self, task_id: str) -> Path:
        return self._events_dir / f"{task_id}.jsonl"

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                os.replace(tmp_path, path)
                return True
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.warning(f"Atomic write failed for {path}: {e}")
            return False

    def save_task(self, task_id: str, task_dict: Dict[str, Any], schema_version: int = CURRENT_SCHEMA_VERSION) -> bool:
        path = self._task_path(task_id)
        record = dict(task_dict)
        record["schema_version"] = schema_version
        record["_persisted_at"] = datetime.now(timezone.utc).isoformat()
        return self._atomic_write(path, record)

    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        path = self._task_path(task_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load task {task_id}: {e}")
            return None

    def delete_task(self, task_id: str) -> bool:
        path = self._task_path(task_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                logger.warning(f"Failed to delete task {task_id}: {e}")
        return False

    def list_tasks(self) -> List[str]:
        if not self._tasks_dir.exists():
            return []
        return [p.stem for p in self._tasks_dir.glob("*.json")]

    def save_event(self, event_dict: Dict[str, Any]) -> bool:
        task_id = event_dict.get("task_id", "")
        if not task_id:
            return False
        path = self._event_path(task_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(event_dict, default=str)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return True
        except Exception as e:
            logger.warning(f"Failed to append event for {task_id}: {e}")
            return False

    def get_events(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        path = self._event_path(task_id)
        if not path.exists():
            return []
        events = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return events[-limit:]
        except Exception as e:
            logger.warning(f"Failed to read events for {task_id}: {e}")
            return []

    def clear(self, task_id: Optional[str] = None) -> int:
        count = 0
        if task_id is None:
            for p in list(self._tasks_dir.glob("*.json")):
                try:
                    p.unlink()
                    count += 1
                except Exception:
                    pass
            for p in list(self._events_dir.glob("*.jsonl")):
                try:
                    p.unlink()
                    count += 1
                except Exception:
                    pass
            return count
        task_path = self._task_path(task_id)
        if task_path.exists():
            try:
                task_path.unlink()
                count += 1
            except Exception:
                pass
        event_path = self._event_path(task_id)
        if event_path.exists():
            try:
                event_path.unlink()
                count += 1
            except Exception:
                pass
        return count

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# EventStore interface
# ---------------------------------------------------------------------------

class EventStore(ABC):
    """Provider-neutral interface for event log persistence."""

    @abstractmethod
    def append(self, event_dict: Dict[str, Any]) -> bool:
        """Append an event. Returns True on success."""
        pass

    @abstractmethod
    def get_events(self, task_id: str, limit: int = 100, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get events for a task."""
        pass

    @abstractmethod
    def clear(self, task_id: Optional[str] = None) -> int:
        """Clear events. Returns count cleared."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store for testing."""

    def __init__(self):
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def append(self, event_dict: Dict[str, Any]) -> bool:
        task_id = event_dict.get("task_id", "")
        self._events.setdefault(task_id, []).append(dict(event_dict))
        return True

    def get_events(self, task_id: str, limit: int = 100, since: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self._events.get(task_id, [])
        if since:
            events = [e for e in events if e.get("timestamp", "") > since]
        return events[-limit:]

    def clear(self, task_id: Optional[str] = None) -> int:
        if task_id is None:
            count = sum(len(v) for v in self._events.values())
            self._events.clear()
            return count
        count = len(self._events.get(task_id, []))
        self._events.pop(task_id, None)
        return count


class FilesystemEventStore(EventStore):
    """Filesystem-backed event store using JSONL."""

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            base_path = user_data_dir() / "events"
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _event_path(self, task_id: str) -> Path:
        return self._base_path / f"{task_id}.jsonl"

    def append(self, event_dict: Dict[str, Any]) -> bool:
        task_id = event_dict.get("task_id", "")
        if not task_id:
            return False
        path = self._event_path(task_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(event_dict, default=str)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return True
        except Exception as e:
            logger.warning(f"Event store append failed: {e}")
            return False

    def get_events(self, task_id: str, limit: int = 100, since: Optional[str] = None) -> List[Dict[str, Any]]:
        path = self._event_path(task_id)
        if not path.exists():
            return []
        events = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            if since is None or event.get("timestamp", "") > since:
                                events.append(event)
                        except json.JSONDecodeError:
                            continue
            return events[-limit:]
        except Exception as e:
            logger.warning(f"Event store read failed: {e}")
            return []

    def clear(self, task_id: Optional[str] = None) -> int:
        if task_id is None:
            count = len(list(self._base_path.glob("*.jsonl")))
            for p in self._base_path.glob("*.jsonl"):
                try:
                    p.unlink()
                except Exception:
                    pass
            return count
        path = self._event_path(task_id)
        if path.exists():
            try:
                path.unlink()
                return 1
            except Exception:
                pass
        return 0


# ---------------------------------------------------------------------------
# TaskPersistenceManager
# ---------------------------------------------------------------------------

class TaskPersistenceManager:
    """
    Orchestration layer around PersistenceBackend and EventStore.

    Responsibilities:
    - Checkpoint tasks at lifecycle boundaries
    - Recover incomplete tasks after crash
    - Security filtering before persistence
    - Failure isolation (never crashes AgentCore)
    - Emit persistence/recovery events via EventBus
    """

    def __init__(
        self,
        backend: Optional[PersistenceBackend] = None,
        event_store: Optional[EventStore] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self._backend = backend or InMemoryPersistenceBackend()
        self._event_store = event_store or InMemoryEventStore()
        self._event_bus = event_bus
        self._checkpoint_enabled = True

    @property
    def backend(self) -> PersistenceBackend:
        return self._backend

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    def set_event_bus(self, event_bus: Optional[EventBus]) -> None:
        self._event_bus = event_bus

    def _emit(self, event_type: EventType, data: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if self._event_bus is None or self._event_bus.subscriber_count == 0:
            return
        try:
            event = create_event(
                event_type=event_type,
                task_id=data.get("task_id", "") if data else "",
                data=data or {},
                metadata=metadata or {},
            )
            self._event_bus.emit(event)
        except Exception:
            logger.debug("Failed to emit persistence event", exc_info=True)

    def _prepare_task_dict(self, task: Task) -> Dict[str, Any]:
        task_dict = task.to_dict()
        return _sanitize_for_persistence(task_dict)

    def checkpoint(self, task: Task) -> None:
        """Checkpoint a task at a lifecycle boundary."""
        if not self._checkpoint_enabled:
            return
        if task.is_terminal():
            return
        task_dict = self._prepare_task_dict(task)
        try:
            success = self._backend.save_task(task.task_id, task_dict)
            if success:
                self._emit(EventType.TASK_STATE_CHANGED, data={
                    "task_id": task.task_id,
                    "current_state": task.current_state.value,
                    "action": "checkpoint",
                })
        except Exception as e:
            logger.warning(f"Task checkpoint failed: {e}")
            self._emit(EventType.RUNTIME_ERROR, data={
                "task_id": task.task_id,
                "error": f"checkpoint_failed: {e}",
                "source": "persistence",
            })

    def save_event(self, event: AgentEvent) -> None:
        """Persist an event to the event store."""
        event_dict = event.to_dict()
        event_dict = _sanitize_for_persistence(event_dict)
        try:
            self._event_store.append(event_dict)
        except Exception as e:
            logger.warning(f"Event store append failed: {e}")

    def load_task(self, task_id: str) -> Optional[Task]:
        """Load a persisted task by ID."""
        try:
            data = self._backend.load_task(task_id)
            if data is None:
                return None
            schema_version = data.get("schema_version")
            if schema_version is None:
                logger.warning(f"Task {task_id} missing schema_version; refusing to load")
                return None
            if schema_version != CURRENT_SCHEMA_VERSION:
                logger.warning(f"Task {task_id} has unsupported schema_version={schema_version}; refusing to load")
                return None
            data.pop("schema_version", None)
            data.pop("_persisted_at", None)
            return Task.from_dict(data)
        except Exception as e:
            logger.warning(f"Task load failed: {e}")
            return None

    def recover_incomplete_tasks(self) -> List[Task]:
        """Recover all non-terminal tasks from persistence."""
        recovered = []
        try:
            for task_id in self._backend.list_tasks():
                task = self.load_task(task_id)
                if task is None:
                    continue
                if not task.is_terminal():
                    recovered.append(task)
                    self._emit(EventType.TASK_STATE_CHANGED, data={
                        "task_id": task_id,
                        "current_state": task.current_state.value,
                        "action": "recovered",
                    })
        except Exception as e:
            logger.warning(f"Task recovery failed: {e}")
        return recovered

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and its events from persistence."""
        try:
            task_deleted = self._backend.delete_task(task_id)
            event_cleared = self._event_store.clear(task_id)
            return task_deleted or event_cleared > 0
        except Exception as e:
            logger.warning(f"Task delete failed: {e}")
            return False

    def get_task_events(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get persisted events for a task."""
        try:
            return self._event_store.get_events(task_id, limit=limit)
        except Exception as e:
            logger.warning(f"Failed to get task events: {e}")
            return []

    def close(self) -> None:
        """Close underlying resources."""
        try:
            if hasattr(self._backend, 'close'):
                self._backend.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def create_persistence_manager(
    backend: Optional[PersistenceBackend] = None,
    event_store: Optional[EventStore] = None,
    event_bus: Optional[EventBus] = None,
    use_filesystem: bool = False,
    base_path: Optional[Path] = None,
) -> TaskPersistenceManager:
    """Create a TaskPersistenceManager with optional filesystem backends.

    If use_filesystem is True, creates FilesystemPersistenceBackend and
    FilesystemEventStore under base_path (defaults to user_data_dir()).
    """
    if use_filesystem:
        fs_backend = FilesystemPersistenceBackend(base_path=base_path)
        fs_event_store = FilesystemEventStore(base_path=base_path)
        return TaskPersistenceManager(
            backend=fs_backend,
            event_store=fs_event_store,
            event_bus=event_bus,
        )
    if backend is None:
        backend = InMemoryPersistenceBackend()
    if event_store is None:
        event_store = InMemoryEventStore()
    return TaskPersistenceManager(
        backend=backend,
        event_store=event_store,
        event_bus=event_bus,
    )
