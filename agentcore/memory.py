"""
Memory abstraction layer for AgentCore.

Architecture:
    AgentCore
        |
        v
    MemoryManager  (orchestration + failure isolation + normalization)
        |
        ├── MemoryBackend  (abstract provider interface)
        │   ├── DBObsidianBackend  (adapter)
        │   ├── InMemoryBackend    (test/default)
        │   └── future backends...
        |
        ├── MemoryRecord  (structured record)
        └── MemoryType    (enum: TASK, PROJECT, CONVERSATION, DECISION, FACT, ERROR, LEARNING)

Memory is optional. If the backend fails, AgentCore logs and continues.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories that can be stored."""
    TASK = "task"
    PROJECT = "project"
    CONVERSATION = "conversation"
    DECISION = "decision"
    FACT = "fact"
    ERROR = "error"
    LEARNING = "learning"


@dataclass
class MemoryRecord:
    """
    Structured memory record.

    All fields are JSON-serializable via to_dict().
    """
    id: str = field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:12]}")
    content: str = ""
    memory_type: str = MemoryType.FACT.value
    source: str = "agent"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.0
    project: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "type": self.memory_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "relevance": self.relevance,
            "project": self.project,
        }


# Patterns that suggest sensitive data — conservative, deterministic filtering
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


class MemoryBackend(ABC):
    """
    Abstract memory backend interface.

    Provider-neutral. Implementations include:
    - InMemoryBackend (testing/default)
    - DBObsidianBackend (SQLite + Obsidian vault)
    - Future: remote memory providers, SQLite-only, etc.

    Optional methods (delete, clear, close) should be called via hasattr()
    or try/except by MemoryManager — backends are not required to implement them.
    """

    @abstractmethod
    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[dict[str, Any]]:
        """Search for memories matching the query."""
        pass

    @abstractmethod
    def store(self, type: str, content: str, project: Optional[str] = None, importance: float = 0.5) -> dict[str, Any]:
        """Store a memory record."""
        pass

    @abstractmethod
    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        """Update a memory record's content."""
        pass

    @abstractmethod
    def list(self, project: Optional[str] = None, type: Optional[str] = None, limit: int = 50) -> List[dict[str, Any]]:
        """List memory records with optional filtering."""
        pass

    def delete(self, memory_id: str) -> bool:
        """Delete a memory record. Optional — default: not supported."""
        return False

    def clear(self, project: Optional[str] = None) -> int:
        """Clear memories, optionally scoped to a project. Optional — default: not supported."""
        return 0

    def close(self) -> None:
        """Close any underlying resources. Optional — default: no-op."""
        pass


class MemoryManager:
    """
    Orchestration layer around MemoryBackend.

    Responsibilities:
    - Normalize backend results to consistent dict format
    - Limit memory context size
    - Handle backend failures gracefully (log + continue)
    - Emit events via EventBus if available
    - Filter potentially sensitive data

    The Manager does NOT know SQL, Obsidian vault layout, or SQLite schemas.
    """

    def __init__(self, backend: Optional[MemoryBackend] = None, event_bus=None,
                 max_context_records: int = 10, max_content_chars: int = 2000):
        self._backend = backend
        self._event_bus = event_bus
        self._max_context_records = max_context_records
        self._max_content_chars = max_content_chars
        self._enabled = backend is not None

    @property
    def enabled(self) -> bool:
        """Whether memory is available and usable."""
        return self._enabled and self._backend is not None

    @property
    def max_context_records(self) -> int:
        return self._max_context_records

    def set_event_bus(self, event_bus) -> None:
        """Attach an event bus after construction."""
        self._event_bus = event_bus

    def _emit(self, event_type, data=None, metadata=None, task_id="", iteration=None):
        """Emit a memory event if event bus is available."""
        if self._event_bus is None or self._event_bus.subscriber_count == 0:
            return
        try:
            from agentcore.events import create_event, EventType
            # Map string event_type to EventType
            if isinstance(event_type, str):
                event_type = EventType(event_type)
            event = create_event(
                event_type=event_type,
                task_id=task_id,
                iteration=iteration,
                data=data or {},
                metadata=metadata or {},
            )
            self._event_bus.emit(event)
        except Exception:
            logger.debug("Failed to emit memory event", exc_info=True)

    def search(self, query: str, project: Optional[str] = None, limit: int = 20,
               task_id: str = "", iteration: Optional[int] = None) -> List[dict[str, Any]]:
        """
        Search for relevant memories.

        Returns an empty list on backend failure — never raises.
        """
        if not self.enabled:
            return []

        effective_limit = min(limit, self._max_context_records)

        self._emit("memory.recall.started", metadata={
            "query": query[:200],
            "project": project or "",
        }, task_id=task_id, iteration=iteration)

        start = time.time()
        try:
            results = self._backend.search(query, project, limit=effective_limit)
            duration = time.time() - start

            # Normalize results
            normalized = []
            for r in results:
                if isinstance(r, dict):
                    normalized.append({
                        "id": r.get("id", ""),
                        "content": r.get("content", "")[:self._max_content_chars],
                        "type": r.get("type", r.get("memory_type", "")),
                        "project": r.get("project", project or ""),
                        "relevance": r.get("relevance", r.get("score", 0.0)),
                        "timestamp": r.get("timestamp", r.get("created_at", "")),
                    })
                else:
                    normalized.append({"content": str(r)[:self._max_content_chars]})

            self._emit("memory.recall.completed", data={
                "result_count": len(normalized),
                "duration": round(duration, 3),
                "success": True,
            }, task_id=task_id, iteration=iteration)

            return normalized

        except Exception as e:
            duration = time.time() - start
            logger.warning(f"Memory search failed: {e}")
            self._emit("memory.error", data={
                "operation": "search",
                "error": str(e),
                "duration": round(duration, 3),
            }, task_id=task_id, iteration=iteration)
            return []

    def store(self, type: str, content: str, project: Optional[str] = None,
              importance: float = 0.5,
              task_id: str = "", iteration: Optional[int] = None) -> Optional[dict[str, Any]]:
        """
        Store a memory record.

        Filters sensitive content. Returns stored record dict or None on failure.
        Never raises.
        """
        if not self.enabled:
            return None

        # Security: don't store sensitive data
        if _contains_sensitive_data(content):
            logger.warning("Skipping memory storage: potentially sensitive content detected")
            return None

        # Limit content size
        content = content[:self._max_content_chars]

        self._emit("memory.store.started", metadata={
            "type": type,
            "project": project or "",
        }, task_id=task_id, iteration=iteration)

        start = time.time()
        try:
            result = self._backend.store(type, content, project, importance)
            duration = time.time() - start

            self._emit("memory.store.completed", data={
                "memory_id": result.get("id", "") if isinstance(result, dict) else "",
                "duration": round(duration, 3),
                "success": True,
            }, task_id=task_id, iteration=iteration)

            return result

        except Exception as e:
            duration = time.time() - start
            logger.warning(f"Memory store failed: {e}")
            self._emit("memory.error", data={
                "operation": "store",
                "error": str(e),
                "duration": round(duration, 3),
            }, task_id=task_id, iteration=iteration)
            return None

    def update(self, memory_id: str, content: str) -> Optional[dict[str, Any]]:
        """Update a memory record. Returns None on failure."""
        if not self.enabled:
            return None
        try:
            return self._backend.update(memory_id, content)
        except Exception as e:
            logger.warning(f"Memory update failed: {e}")
            return None

    def list(self, project: Optional[str] = None, type: Optional[str] = None,
             limit: int = 50) -> List[dict[str, Any]]:
        """List memory records. Returns empty list on failure."""
        if not self.enabled:
            return []
        try:
            return self._backend.list(project, type, limit)
        except Exception as e:
            logger.warning(f"Memory list failed: {e}")
            return []

    def delete(self, memory_id: str) -> bool:
        """Delete a memory record. Returns False on failure."""
        if not self.enabled:
            return False
        try:
            if hasattr(self._backend, 'delete'):
                return self._backend.delete(memory_id)
        except Exception as e:
            logger.warning(f"Memory delete failed: {e}")
        return False

    def clear(self, project: Optional[str] = None) -> int:
        """Clear memories. Returns count of cleared records."""
        if not self.enabled:
            return 0
        try:
            if hasattr(self._backend, 'clear'):
                return self._backend.clear(project)
        except Exception as e:
            logger.warning(f"Memory clear failed: {e}")
        return 0

    def close(self) -> None:
        """Close the backend if it supports closing."""
        if self._backend and hasattr(self._backend, 'close'):
            try:
                self._backend.close()
            except Exception:
                pass

    def store_decision(self, decision: str, project: str, context: Optional[str] = None,
                       task_id: str = "", iteration: Optional[int] = None) -> Optional[dict[str, Any]]:
        """Store a decision memory."""
        content = f"{context}\n\nDecision: {decision}" if context else decision
        return self.store(MemoryType.DECISION.value, content, project=project,
                          importance=0.8, task_id=task_id, iteration=iteration)

    def store_lesson(self, lesson: str, project: str,
                     task_id: str = "", iteration: Optional[int] = None) -> Optional[dict[str, Any]]:
        """Store a lesson learned."""
        return self.store(MemoryType.LEARNING.value, lesson, project=project,
                          importance=0.7, task_id=task_id, iteration=iteration)

    def store_project_architecture(self, architecture: str, project: str,
                                   task_id: str = "", iteration: Optional[int] = None) -> Optional[dict[str, Any]]:
        """Store architecture information."""
        return self.store(MemoryType.PROJECT.value, architecture, project=project,
                          importance=0.9, task_id=task_id, iteration=iteration)

    def retrieve_relevant_memory(self, query: str, project: str,
                                 types: Optional[List[str]] = None,
                                 task_id: str = "", iteration: Optional[int] = None) -> str:
        """Retrieve relevant memories as a formatted string for context."""
        results = self.search(query, project, limit=10, task_id=task_id, iteration=iteration)
        relevant = [r for r in results if types is None or r.get("type") in types]
        return "\n\n---\n\n".join(r.get("content", "") for r in relevant if r.get("content"))

    def store_task_result(self, task_id: str, user_request: str, success: bool,
                          summary: str, project: str,
                          iteration: Optional[int] = None) -> Optional[dict[str, Any]]:
        """Store the outcome of a completed task."""
        content = (
            f"Task: {user_request}\n"
            f"Result: {'SUCCESS' if success else 'FAILED'}\n"
            f"Summary: {summary}"
        )
        return self.store(
            MemoryType.TASK.value, content, project=project,
            importance=0.7 if success else 0.3,
            task_id=task_id, iteration=iteration,
        )


class InMemoryBackend(MemoryBackend):
    """
    Simple in-memory backend for testing and development.

    No external dependencies. Not persistent across process restarts.
    """

    def __init__(self):
        self._records: dict[str, dict[str, Any]] = {}

    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[dict[str, Any]]:
        query_lower = query.lower()
        results = []
        for r in self._records.values():
            if project and r.get("project") != project:
                continue
            content = r.get("content", "")
            if query_lower in content.lower():
                results.append(dict(r))
        return sorted(results, key=lambda x: x.get("importance", 0), reverse=True)[:limit]

    def store(self, type: str, content: str, project: Optional[str] = None,
              importance: float = 0.5) -> dict[str, Any]:
        record = {
            "id": f"mem-{uuid.uuid4().hex[:12]}",
            "type": type,
            "content": content,
            "project": project,
            "importance": importance,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._records[record["id"]] = record
        return record

    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        if memory_id not in self._records:
            return {}
        self._records[memory_id]["content"] = content
        return dict(self._records[memory_id])

    def list(self, project: Optional[str] = None, type: Optional[str] = None,
             limit: int = 50) -> List[dict[str, Any]]:
        results = []
        for r in self._records.values():
            if project and r.get("project") != project:
                continue
            if type and r.get("type") != type:
                continue
            results.append(dict(r))
        return sorted(results, key=lambda x: x.get("importance", 0), reverse=True)[:limit]

    def delete(self, memory_id: str) -> bool:
        if memory_id in self._records:
            del self._records[memory_id]
            return True
        return False

    def clear(self, project: Optional[str] = None) -> int:
        if project:
            to_remove = [k for k, v in self._records.items() if v.get("project") == project]
            for k in to_remove:
                del self._records[k]
            return len(to_remove)
        else:
            count = len(self._records)
            self._records.clear()
            return count

    def close(self) -> None:
        pass
