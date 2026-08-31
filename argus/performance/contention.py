"""Contention and deadlock protection."""

import threading
import time
from typing import Dict, Optional, Set


class ContentionError(Exception):
    """Contention error."""
    pass


class DeadlockError(Exception):
    """Deadlock error."""
    pass


class LockWrapper:
    """Thread-safe lock wrapper with timeout and owner tracking."""

    def __init__(self, name: str, timeout: float = 10.0):
        self.name = name
        self._lock = threading.Lock()
        self._timeout = timeout
        self._owner: Optional[int] = None
        self._wait_count = 0
        self._contention_count = 0

    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire the lock with timeout."""
        timeout = timeout or self._timeout
        self._wait_count += 1

        acquired = self._lock.acquire(blocking=blocking, timeout=timeout)
        if acquired:
            self._owner = threading.current_thread().ident
        else:
            self._contention_count += 1
        return acquired

    def release(self) -> None:
        """Release the lock."""
        self._owner = None
        self._lock.release()

    @property
    def is_locked(self) -> bool:
        """Check if the lock is held."""
        return self._lock.locked()

    @property
    def owner(self) -> Optional[int]:
        """Get the thread ID of the lock owner."""
        return self._owner

    @property
    def wait_count(self) -> int:
        """Get the number of threads that waited for this lock."""
        return self._wait_count

    @property
    def contention_count(self) -> int:
        """Get the number of times contention was detected."""
        return self._contention_count


class ContentionDetector:
    """Detects lock contention and potential deadlocks."""

    def __init__(self, deadlock_timeout: float = 30.0):
        self._deadlock_timeout = deadlock_timeout
        self._lock = threading.Lock()
        self._lock_graph: Dict[int, Set[str]] = {}  # thread_id -> set of lock names
        self._lock_owners: Dict[str, int] = {}  # lock_name -> thread_id
        self._contention_events: list = []

    def record_lock_acquire(self, thread_id: int, lock_name: str) -> None:
        """Record that a thread is acquiring a lock."""
        with self._lock:
            if thread_id not in self._lock_graph:
                self._lock_graph[thread_id] = set()
            self._lock_graph[thread_id].add(lock_name)
            self._lock_owners[lock_name] = thread_id

    def record_lock_release(self, thread_id: int, lock_name: str) -> None:
        """Record that a thread released a lock."""
        with self._lock:
            if thread_id in self._lock_graph:
                self._lock_graph[thread_id].discard(lock_name)
            self._lock_owners.pop(lock_name, None)

    def detect_deadlock(self) -> Optional[list]:
        """Detect potential deadlocks using cycle detection."""
        with self._lock:
            # Simple cycle detection in lock graph
            visited = set()
            for thread_id in self._lock_graph:
                if thread_id not in visited:
                    cycle = self._find_cycle(thread_id, visited, set())
                    if cycle:
                        return cycle
        return None

    def _find_cycle(
        self,
        thread_id: int,
        visited: set,
        path: set,
    ) -> Optional[list]:
        """Find a cycle in the lock graph."""
        if thread_id in path:
            return [thread_id]
        if thread_id in visited:
            return None

        visited.add(thread_id)
        path.add(thread_id)

        for lock_name in self._lock_graph.get(thread_id, set()):
            owner = self._lock_owners.get(lock_name)
            if owner and owner != thread_id:
                cycle = self._find_cycle(owner, visited, path)
                if cycle:
                    return [thread_id] + cycle

        path.discard(thread_id)
        return None

    def record_contention(self, lock_name: str, wait_time: float) -> None:
        """Record a contention event."""
        with self._lock:
            self._contention_events.append({
                "lock_name": lock_name,
                "wait_time": wait_time,
                "timestamp": time.monotonic(),
            })

    def get_contention_events(self) -> list:
        """Get all recorded contention events."""
        with self._lock:
            return list(self._contention_events)

    def clear_events(self) -> None:
        """Clear all contention events."""
        with self._lock:
            self._contention_events.clear()
