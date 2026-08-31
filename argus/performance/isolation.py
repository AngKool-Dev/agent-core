"""Isolation guarantees for concurrent execution."""

import threading
from typing import Any, Dict, Optional


class IsolationError(Exception):
    """Isolation error."""
    pass


class ExecutionContext:
    """Isolated execution context for a single run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._state: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the context."""
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the context."""
        with self._lock:
            self._state[key] = value

    def update(self, key: str, value: Any) -> None:
        """Update a value in the context."""
        with self._lock:
            self._state[key] = value

    def delete(self, key: str) -> None:
        """Delete a value from the context."""
        with self._lock:
            self._state.pop(key, None)

    def clear(self) -> None:
        """Clear all values in the context."""
        with self._lock:
            self._state.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Get a copy of the context as a dict."""
        with self._lock:
            return dict(self._state)


class IsolationManager:
    """Manages isolation between concurrent runs."""

    def __init__(self):
        self._contexts: Dict[str, ExecutionContext] = {}
        self._lock = threading.Lock()

    def create_context(self, run_id: str) -> ExecutionContext:
        """Create an isolated context for a run."""
        with self._lock:
            if run_id in self._contexts:
                raise IsolationError(f"Context already exists for run {run_id}")
            context = ExecutionContext(run_id)
            self._contexts[run_id] = context
            return context

    def get_context(self, run_id: str) -> Optional[ExecutionContext]:
        """Get the context for a run."""
        with self._lock:
            return self._contexts.get(run_id)

    def remove_context(self, run_id: str) -> bool:
        """Remove a context."""
        with self._lock:
            if run_id in self._contexts:
                del self._contexts[run_id]
                return True
            return False

    def has_context(self, run_id: str) -> bool:
        """Check if a context exists."""
        with self._lock:
            return run_id in self._contexts

    def list_contexts(self) -> list:
        """List all active context IDs."""
        with self._lock:
            return list(self._contexts.keys())

    def clear_all(self) -> None:
        """Clear all contexts."""
        with self._lock:
            self._contexts.clear()
