"""Tests for ARGUS Performance scheduler."""

import threading
import time

import pytest

from argus.performance.scheduler import BoundedScheduler, SchedulerError, TaskHandle
from argus.performance.models import ConcurrencyPolicy, ConcurrencyMode


class TestBoundedScheduler:
    """Tests for BoundedScheduler."""

    def setup_method(self):
        self.scheduler = BoundedScheduler(max_workers=2)
        self.scheduler.start()

    def teardown_method(self):
        self.scheduler.stop(wait=False)

    def test_start_and_stop(self):
        scheduler = BoundedScheduler(max_workers=2)
        scheduler.start()
        assert scheduler.is_shutdown is False
        scheduler.stop()
        assert scheduler.is_shutdown is True

    def test_submit_task(self):
        def simple_task():
            return 42

        handle = self.scheduler.submit(simple_task)
        assert handle is not None
        assert handle.task_id
        result = handle.future.result(timeout=5)
        assert result == 42

    def test_submit_multiple_tasks(self):
        def simple_task(x):
            return x * 2

        handles = [self.scheduler.submit(simple_task, i) for i in range(5)]
        results = [h.future.result(timeout=5) for h in handles]
        assert results == [0, 2, 4, 6, 8]

    def test_task_with_args(self):
        def add(a, b):
            return a + b

        handle = self.scheduler.submit(add, 3, 4)
        result = handle.future.result(timeout=5)
        assert result == 7

    def test_task_with_kwargs(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        handle = self.scheduler.submit(greet, "World", greeting="Hi")
        result = handle.future.result(timeout=5)
        assert result == "Hi, World!"

    def test_custom_task_id(self):
        def task():
            return 42

        handle = self.scheduler.submit(task, task_id="custom-id")
        assert handle.task_id == "custom-id"

    def test_cancel_queued_task(self):
        """Cancel a task that hasn't started yet."""
        barrier = threading.Event()

        def blocking_task():
            barrier.wait(timeout=5)
            return 42

        # Fill up workers
        handle1 = self.scheduler.submit(blocking_task)
        handle2 = self.scheduler.submit(blocking_task)

        # This task should be queued
        def quick_task():
            return 1

        handle3 = self.scheduler.submit(quick_task, task_id="cancel-me")

        # Cancel the queued task
        cancelled = self.scheduler.cancel("cancel-me")
        assert cancelled is True

        # Release blocking tasks
        barrier.set()
        handle1.future.result(timeout=5)
        handle2.future.result(timeout=5)

    def test_get_task_status(self):
        def task():
            time.sleep(0.1)
            return 42

        handle = self.scheduler.submit(task, task_id="status-test")
        status = self.scheduler.get_task_status("status-test")
        assert status in ["queued", "running", "completed"]

    def test_get_task_status_nonexistent(self):
        status = self.scheduler.get_task_status("nonexistent")
        assert status is None

    def test_measure_concurrency(self):
        measurement = self.scheduler.measure_concurrency()
        assert measurement.max_concurrency == 2

    def test_active_task_count(self):
        assert self.scheduler.active_task_count >= 0

    def test_queued_task_count(self):
        assert self.scheduler.queued_task_count >= 0

    def test_submit_after_shutdown(self):
        scheduler = BoundedScheduler(max_workers=1)
        scheduler.start()
        scheduler.stop()
        with pytest.raises(SchedulerError):
            scheduler.submit(lambda: None)


class TestTaskHandle:
    """Tests for TaskHandle."""

    def test_wait_time(self):
        handle = TaskHandle("test", None)
        time.sleep(0.01)
        assert handle.wait_time > 0

    def test_execution_time_before_start(self):
        handle = TaskHandle("test", None)
        assert handle.execution_time == 0.0
