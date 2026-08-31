"""Concurrency policy and bounded scheduler."""

import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from argus.performance.models import (
    BackpressureAction,
    ConcurrencyMeasurement,
    ConcurrencyMode,
    ConcurrencyPolicy,
)
from argus.performance.resources import ResourceController, ResourceType


class SchedulerError(Exception):
    """Scheduler error."""
    pass


class TaskHandle:
    """Handle for a scheduled task."""

    def __init__(self, task_id: str, future: Future):
        self.task_id = task_id
        self.future = future
        self.created_at = time.monotonic()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None

    @property
    def wait_time(self) -> float:
        """Time spent waiting in queue."""
        if self.started_at is None:
            return time.monotonic() - self.created_at
        return self.started_at - self.created_at

    @property
    def execution_time(self) -> float:
        """Time spent executing."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at if self.completed_at is not None else time.monotonic()
        return end - self.started_at


class BoundedScheduler:
    """Bounded concurrent scheduler with backpressure."""

    def __init__(
        self,
        policy: Optional[ConcurrencyPolicy] = None,
        resource_controller: Optional[ResourceController] = None,
        max_workers: int = 4,
    ):
        self._policy = policy or ConcurrencyPolicy()
        self._resource_controller = resource_controller
        self._max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._task_queue: deque = deque()
        self._active_tasks: Dict[str, TaskHandle] = {}
        self._completed_tasks: Dict[str, TaskHandle] = {}
        self._lock = threading.Lock()
        self._shutdown = False
        self._task_counter = 0

    def start(self) -> None:
        """Start the scheduler."""
        with self._lock:
            if self._executor is not None:
                return
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="argus-scheduler",
            )
            self._shutdown = False

    def stop(self, wait: bool = True, timeout: float = 30.0) -> None:
        """Stop the scheduler."""
        with self._lock:
            self._shutdown = True
            if self._executor is not None:
                self._executor.shutdown(wait=wait)
                self._executor = None

    def submit(
        self,
        fn: Callable,
        *args: Any,
        task_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[TaskHandle]:
        """Submit a task for execution."""
        with self._lock:
            if self._shutdown:
                raise SchedulerError("Scheduler is shut down")

            if self._executor is None:
                self.start()

            # Check queue capacity
            if len(self._task_queue) >= self._policy.max_queue_size:
                return None

            # Generate task ID
            if task_id is None:
                self._task_counter += 1
                task_id = f"task-{self._task_counter}-{uuid.uuid4().hex[:8]}"

            # Create future and submit
            future = self._executor.submit(self._wrap_task(fn, task_id), *args, **kwargs)
            handle = TaskHandle(task_id, future)
            self._task_queue.append(handle)
            self._active_tasks[task_id] = handle

            return handle

    def _wrap_task(self, fn: Callable, task_id: str) -> Callable:
        """Wrap a task to track timing."""
        def wrapper(*args, **kwargs):
            handle = self._active_tasks.get(task_id)
            if handle:
                handle.started_at = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                return result
            finally:
                if handle:
                    handle.completed_at = time.monotonic()
                    with self._lock:
                        self._completed_tasks[task_id] = handle
                        self._active_tasks.pop(task_id, None)
        return wrapper

    def cancel(self, task_id: str) -> bool:
        """Cancel a task if it hasn't started."""
        with self._lock:
            handle = self._active_tasks.get(task_id)
            if handle is None:
                return False
            return handle.future.cancel()

    def get_task_status(self, task_id: str) -> Optional[str]:
        """Get the status of a task."""
        with self._lock:
            handle = self._active_tasks.get(task_id) or self._completed_tasks.get(task_id)
            if handle is None:
                return None
            if handle.future.cancelled():
                return "cancelled"
            if handle.future.done():
                return "completed"
            if handle.started_at is not None:
                return "running"
            return "queued"

    def measure_concurrency(self) -> ConcurrencyMeasurement:
        """Get current concurrency measurement."""
        with self._lock:
            return ConcurrencyMeasurement(
                active_operations=len([
                    t for t in self._active_tasks.values()
                    if t.started_at is not None and t.completed_at is None
                ]),
                queued_operations=len(self._task_queue),
                completed_operations=len(self._completed_tasks),
                max_concurrency=self._max_workers,
            )

    @property
    def is_shutdown(self) -> bool:
        """Check if scheduler is shut down."""
        return self._shutdown

    @property
    def active_task_count(self) -> int:
        """Get number of active tasks."""
        with self._lock:
            return len(self._active_tasks)

    @property
    def queued_task_count(self) -> int:
        """Get number of queued tasks."""
        with self._lock:
            return len(self._task_queue)
