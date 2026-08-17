"""
Tests for AgentCore task registry and locking (Phase 8).
"""

import pytest
from threading import Thread

from agentcore.task_registry import (
    TaskRegistry,
    TaskRecord,
    TaskRecordStatus,
)
from agentcore.task import Task, TaskState
from agentcore.events import EventBus, EventType
from agentcore.errors import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskLockError,
)


def _make_task(task_id: str = "task-1", user_request: str = "Test task", project: str = "test-project", state: TaskState = TaskState.CREATED) -> Task:
    task = Task(task_id=task_id, user_request=user_request, project=project)
    task.current_state = state
    return task


class TestTaskRegistry:
    def test_register_task(self):
        registry = TaskRegistry()
        task = _make_task()
        record = registry.register(task)
        assert record.task_id == task.task_id
        assert record.status == TaskRecordStatus.REGISTERED

    def test_register_duplicate_task_updates_record(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        record = registry.register(task)
        assert record.task_id == task.task_id

    def test_get_task(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        record = registry.get(task.task_id)
        assert record is not None
        assert record.task_id == task.task_id

    def test_get_missing_task_returns_none(self):
        registry = TaskRegistry()
        assert registry.get("nonexistent") is None

    def test_list_tasks(self):
        registry = TaskRegistry()
        registry.register(_make_task(task_id="t1"))
        registry.register(_make_task(task_id="t2"))
        tasks = registry.list_tasks()
        assert len(tasks) == 2
        assert {t.task_id for t in tasks} == {"t1", "t2"}

    def test_remove_task(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        assert registry.remove(task.task_id) is True
        assert registry.get(task.task_id) is None
        assert registry.remove(task.task_id) is False

    def test_update_status(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.update_status(task.task_id, TaskRecordStatus.RUNNING)
        record = registry.get(task.task_id)
        assert record.status == TaskRecordStatus.RUNNING

    def test_update_task_state(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.update_task_state(task.task_id, TaskState.RUNNING)
        record = registry.get(task.task_id)
        assert record.task_state == TaskState.RUNNING


class TestTaskRegistryLocking:
    def test_acquire_lock(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        assert registry.acquire_lock(task.task_id, "holder-1") is True

    def test_acquire_lock_twice_same_holder_succeeds(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.acquire_lock(task.task_id, "holder-1")
        assert registry.acquire_lock(task.task_id, "holder-1") is True

    def test_acquire_lock_different_holder_fails(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.acquire_lock(task.task_id, "holder-1")
        with pytest.raises(TaskAlreadyRunningError):
            registry.acquire_lock(task.task_id, "holder-2")

    def test_acquire_lock_for_missing_task_fails(self):
        registry = TaskRegistry()
        with pytest.raises(TaskNotFoundError):
            registry.acquire_lock("nonexistent", "holder-1")

    def test_release_lock(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.acquire_lock(task.task_id, "holder-1")
        assert registry.release_lock(task.task_id, "holder-1") is True
        assert registry.is_locked(task.task_id) is False

    def test_release_lock_wrong_holder_fails(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.acquire_lock(task.task_id, "holder-1")
        assert registry.release_lock(task.task_id, "holder-2") is False

    def test_release_lock_twice_safe(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.acquire_lock(task.task_id, "holder-1")
        registry.release_lock(task.task_id, "holder-1")
        assert registry.release_lock(task.task_id, "holder-1") is False

    def test_force_release_lock(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        registry.acquire_lock(task.task_id, "holder-1")
        assert registry.force_release_lock(task.task_id) is True
        assert registry.is_locked(task.task_id) is False

    def test_force_release_unlocked_task(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        assert registry.force_release_lock(task.task_id) is False

    def test_is_locked(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)
        assert registry.is_locked(task.task_id) is False
        registry.acquire_lock(task.task_id, "holder-1")
        assert registry.is_locked(task.task_id) is True
        registry.release_lock(task.task_id, "holder-1")
        assert registry.is_locked(task.task_id) is False


class TestTaskRegistryActiveFiltering:
    def test_list_active(self):
        registry = TaskRegistry()
        t1 = _make_task(task_id="t1")
        t2 = _make_task(task_id="t2", state=TaskState.COMPLETED)
        registry.register(t1)
        registry.register(t2)
        active = registry.list_active()
        assert len(active) == 1
        assert active[0].task_id == "t1"

    def test_list_terminal(self):
        registry = TaskRegistry()
        t1 = _make_task(task_id="t1")
        t2 = _make_task(task_id="t2", state=TaskState.COMPLETED)
        registry.register(t1)
        registry.register(t2)
        terminal = registry.list_terminal()
        assert len(terminal) == 1
        assert terminal[0].task_id == "t2"

    def test_list_resumable(self):
        registry = TaskRegistry()
        t1 = _make_task(task_id="t1")
        t2 = _make_task(task_id="t2", state=TaskState.RUNNING)
        registry.register(t1)
        registry.register(t2)
        registry.acquire_lock(t2.task_id, "holder-1")
        resumable = registry.list_resumable()
        assert len(resumable) == 1
        assert resumable[0].task_id == "t1"


class TestTaskRegistryEvents:
    def test_register_emits_event(self):
        bus = EventBus()
        registry = TaskRegistry(event_bus=bus)
        task = _make_task()
        events = []
        bus.subscribe(lambda e: events.append(e))
        registry.register(task)
        assert any(e.event_type == EventType.TASK_REGISTERED for e in events)

    def test_lock_emits_event(self):
        bus = EventBus()
        registry = TaskRegistry(event_bus=bus)
        task = _make_task()
        registry.register(task)
        events = []
        bus.subscribe(lambda e: events.append(e))
        registry.acquire_lock(task.task_id, "holder-1")
        assert any(e.event_type == EventType.TASK_LOCKED for e in events)

    def test_unlock_emits_event(self):
        bus = EventBus()
        registry = TaskRegistry(event_bus=bus)
        task = _make_task()
        registry.register(task)
        events = []
        bus.subscribe(lambda e: events.append(e))
        registry.acquire_lock(task.task_id, "holder-1")
        registry.release_lock(task.task_id, "holder-1")
        assert any(e.event_type == EventType.TASK_UNLOCKED for e in events)

    def test_events_have_correct_task_id(self):
        bus = EventBus()
        registry = TaskRegistry(event_bus=bus)
        task = _make_task(task_id="specific-task")
        events = []
        bus.subscribe(lambda e: events.append(e))
        registry.register(task)
        task_ids = {e.task_id for e in events}
        assert "specific-task" in task_ids


class TestTaskRegistryThreadSafety:
    def test_concurrent_lock_attempts(self):
        registry = TaskRegistry()
        task = _make_task()
        registry.register(task)

        results = []

        def attempt_lock(holder):
            try:
                registry.acquire_lock(task.task_id, holder)
                results.append(("acquired", holder))
            except TaskAlreadyRunningError:
                results.append(("rejected", holder))

        threads = [Thread(target=attempt_lock, args=(f"holder-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        acquired = [r for r in results if r[0] == "acquired"]
        rejected = [r for r in results if r[0] == "rejected"]
        assert len(acquired) == 1
        assert len(rejected) == 4

    def test_concurrent_registrations(self):
        registry = TaskRegistry()

        def register_task(tid):
            t = _make_task(task_id=tid)
            registry.register(t)

        threads = [Thread(target=register_task, args=(f"task-{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(registry.list_tasks()) == 10
