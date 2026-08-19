"""
Tests for automated memory harvesting integration (Phase 5D).

Verifies:
* COMPLETED task automatically triggers harvesting
* FAILED task automatically triggers harvesting
* CANCELLED task automatically triggers harvesting
* non-terminal events do not trigger harvesting
* harvesting runs asynchronously
* harvesting failure does not change task state
* completed task remains COMPLETED when harvesting fails
* failed task remains FAILED when harvesting fails
* duplicate terminal event does not create duplicate memories
* multiple tasks harvest independently
* observations are available before harvesting
* harvesting completion event is emitted
* harvesting failure event is emitted
* manual harvest API works
* manual harvest is idempotent
* no observation/memory cross-contamination between tasks
* coordinator without harvester still works
* disabled harvesting works correctly
"""

import time

from agentcore.desktop_task_coordinator import DesktopTaskCoordinator
from agentcore.events import AgentEvent, EventBus, EventType
from agentcore.memory import InMemoryBackend, MemoryBackend
from agentcore.observations import (
    InMemoryObservationStore,
    Observation,
)
from agentcore.persistence import (
    FilesystemPersistenceBackend,
    InMemoryEventStore,
    TaskPersistenceManager,
)
from agentcore.task import TaskState
from agentcore.task_registry import TaskRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CapturingBus(EventBus):
    """EventBus that captures emitted events for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.emitted.append(event)
        super().emit(event)


def _make_coordinator(tmp_path, observation_store=None, memory_backend=None):
    backend = FilesystemPersistenceBackend(str(tmp_path / "tasks"))
    event_store = InMemoryEventStore()
    persistence = TaskPersistenceManager(backend=backend, event_store=event_store)
    registry = TaskRegistry(persistence=persistence)
    bus = _CapturingBus()
    coordinator = DesktopTaskCoordinator(
        task_registry=registry,
        persistence=persistence,
        event_bus=bus,
        observation_store=observation_store,
        memory_backend=memory_backend,
    )
    coordinator.start()
    return coordinator, registry, persistence, bus


def _make_terminal_event(
    event_type, session_id="session-abc", task_id="turn-001", turn_id="turn-001"
):
    return AgentEvent(
        event_type=event_type,
        metadata={"session_id": session_id, "task_id": task_id, "turn_id": turn_id},
    )


def _wait_for_harvest(bus, task_id, timeout=2.0):
    """Wait for a harvest completion event for a specific task."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for event in bus.emitted:
            if event.task_id == task_id and event.event_type in (
                EventType.MEMORY_HARVEST_COMPLETED,
                EventType.MEMORY_HARVEST_FAILED,
            ):
                return event
        time.sleep(0.05)
    return None


# ---------------------------------------------------------------------------
# Test 1: COMPLETED task automatically triggers harvesting
# ---------------------------------------------------------------------------


def test_completed_task_triggers_harvesting(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    # Register task first
    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    # Complete task
    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    # Wait for harvest event
    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id)
    assert harvest_event is not None
    assert harvest_event.event_type == EventType.MEMORY_HARVEST_COMPLETED
    assert harvest_event.data["candidate_count"] >= 0

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 2: FAILED task automatically triggers harvesting
# ---------------------------------------------------------------------------


def test_failed_task_triggers_harvesting(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    fail_event = _make_terminal_event(EventType.TASK_FAILED)
    coordinator._on_event(fail_event)

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id)
    assert harvest_event is not None
    assert harvest_event.event_type == EventType.MEMORY_HARVEST_COMPLETED

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 3: CANCELLED task automatically triggers harvesting
# ---------------------------------------------------------------------------


def test_cancelled_task_triggers_harvesting(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    cancel_event = _make_terminal_event(EventType.TASK_CANCELLED)
    coordinator._on_event(cancel_event)

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id)
    assert harvest_event is not None
    assert harvest_event.event_type == EventType.MEMORY_HARVEST_COMPLETED

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 4: non-terminal events do not trigger harvesting
# ---------------------------------------------------------------------------


def test_non_terminal_events_do_not_trigger_harvesting(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    started_event = _make_terminal_event(EventType.TASK_STARTED)
    coordinator._on_event(started_event)

    time.sleep(0.2)

    harvest_events = [
        e
        for e in bus.emitted
        if e.event_type
        in (
            EventType.MEMORY_HARVEST_COMPLETED,
            EventType.MEMORY_HARVEST_FAILED,
        )
    ]
    assert len(harvest_events) == 0

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 5: harvesting runs asynchronously
# ---------------------------------------------------------------------------


def test_harvesting_runs_async(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    start = time.time()
    coordinator._on_event(complete_event)

    # Should return quickly (async)
    elapsed = time.time() - start
    assert elapsed < 0.5

    # Harvest should complete eventually
    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id, timeout=3.0)
    assert harvest_event is not None

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 6: harvesting failure does not change task state
# ---------------------------------------------------------------------------


def test_harvest_failure_does_not_change_task_state(tmp_path):
    class FailingBackend(MemoryBackend):
        def search(self, query, project=None, limit=20):
            return []

        def store(self, type, content, project=None, importance=0.5):
            raise RuntimeError("db dead")

        def update(self, memory_id, content):
            return {}

        def list(self, project=None, type=None, limit=50):
            return []

    store = InMemoryObservationStore()
    backend = FailingBackend()
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    time.sleep(0.5)

    task_id = "hermes-session-abc-turn-001"
    record = registry.get(task_id)
    assert record is not None
    assert record.task_state == TaskState.COMPLETED

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 7: completed task remains COMPLETED when harvesting fails
# ---------------------------------------------------------------------------


def test_completed_task_remains_completed_on_harvest_failure(tmp_path):
    class FailingBackend(MemoryBackend):
        def search(self, query, project=None, limit=20):
            return []

        def store(self, type, content, project=None, importance=0.5):
            raise RuntimeError("db dead")

        def update(self, memory_id, content):
            return {}

        def list(self, project=None, type=None, limit=50):
            return []

    store = InMemoryObservationStore()
    backend = FailingBackend()
    coordinator, registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    # Add a meaningful observation so harvesting produces a candidate
    store.add(
        Observation(
            id="obs-1",
            task_id="hermes-session-abc-turn-001",
            session_id="session-abc",
            observation_type="task.completed",
            payload={"result": "Something completed"},
        )
    )

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    time.sleep(0.5)

    task_id = "hermes-session-abc-turn-001"
    record = registry.get(task_id)
    assert record.task_state == TaskState.COMPLETED

    # Harvest failure event should be emitted
    harvest_events = [e for e in bus.emitted if e.event_type == EventType.MEMORY_HARVEST_FAILED]
    assert len(harvest_events) >= 1

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 8: failed task remains FAILED when harvesting fails
# ---------------------------------------------------------------------------


def test_failed_task_remains_failed_on_harvest_failure(tmp_path):
    class FailingBackend(MemoryBackend):
        def search(self, query, project=None, limit=20):
            return []

        def store(self, type, content, project=None, importance=0.5):
            raise RuntimeError("db dead")

        def update(self, memory_id, content):
            return {}

        def list(self, project=None, type=None, limit=50):
            return []

    store = InMemoryObservationStore()
    backend = FailingBackend()
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    fail_event = _make_terminal_event(EventType.TASK_FAILED)
    coordinator._on_event(fail_event)

    time.sleep(0.5)

    task_id = "hermes-session-abc-turn-001"
    record = registry.get(task_id)
    assert record.task_state == TaskState.FAILED

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 9: duplicate terminal event does not create duplicate memories
# ---------------------------------------------------------------------------


def test_duplicate_terminal_event_no_duplicate_memories(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)
    coordinator._on_event(complete_event)  # duplicate

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id, timeout=3.0)
    assert harvest_event is not None

    # Should only have one harvest completion event for this task
    harvest_completions = [
        e
        for e in bus.emitted
        if e.task_id == task_id and e.event_type == EventType.MEMORY_HARVEST_COMPLETED
    ]
    assert len(harvest_completions) == 1

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 10: multiple tasks harvest independently
# ---------------------------------------------------------------------------


def test_multiple_tasks_harvest_independently(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    # Task A
    reg_a = AgentEvent(
        event_type=EventType.TASK_REGISTERED,
        metadata={"session_id": "s1", "task_id": "t1", "turn_id": "t1"},
    )
    coordinator._on_event(reg_a)
    comp_a = AgentEvent(
        event_type=EventType.TASK_COMPLETED,
        metadata={"session_id": "s1", "task_id": "t1", "turn_id": "t1"},
    )
    coordinator._on_event(comp_a)

    # Task B
    reg_b = AgentEvent(
        event_type=EventType.TASK_REGISTERED,
        metadata={"session_id": "s2", "task_id": "t2", "turn_id": "t2"},
    )
    coordinator._on_event(reg_b)
    fail_b = AgentEvent(
        event_type=EventType.TASK_FAILED,
        metadata={"session_id": "s2", "task_id": "t2", "turn_id": "t2"},
    )
    coordinator._on_event(fail_b)

    task_a_id = "hermes-s1-t1"
    task_b_id = "hermes-s2-t2"

    harvest_a = _wait_for_harvest(bus, task_a_id, timeout=3.0)
    harvest_b = _wait_for_harvest(bus, task_b_id, timeout=3.0)

    assert harvest_a is not None
    assert harvest_b is not None
    assert harvest_a.task_id == task_a_id
    assert harvest_b.task_id == task_b_id

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 11: observations are available before harvesting
# ---------------------------------------------------------------------------


def test_observations_available_before_harvesting(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    # Add an observation manually before completion
    store.add(
        Observation(
            id="obs-1",
            task_id="hermes-session-abc-turn-001",
            session_id="session-abc",
            observation_type="task.started",
            payload={"info": "test"},
        )
    )

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id, timeout=3.0)
    assert harvest_event is not None

    # Manual harvest should see the pre-added observation
    result = coordinator.harvest_task(task_id)
    assert result is not None
    assert result["observations_processed"] >= 1

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 12: harvesting completion event is emitted
# ---------------------------------------------------------------------------


def test_harvest_completion_event_emitted(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id)
    assert harvest_event is not None
    assert harvest_event.event_type == EventType.MEMORY_HARVEST_COMPLETED
    assert "candidate_count" in harvest_event.data
    assert "observations_processed" in harvest_event.data
    assert "success" in harvest_event.metadata
    assert harvest_event.metadata["success"] is True

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 13: harvesting failure event is emitted
# ---------------------------------------------------------------------------


def test_harvest_failure_event_emitted(tmp_path):
    class FailingBackend(MemoryBackend):
        def search(self, query, project=None, limit=20):
            return []

        def store(self, type, content, project=None, importance=0.5):
            raise RuntimeError("db dead")

        def update(self, memory_id, content):
            return {}

        def list(self, project=None, type=None, limit=50):
            return []

    store = InMemoryObservationStore()
    backend = FailingBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    # Add a meaningful observation so harvesting produces a candidate
    store.add(
        Observation(
            id="obs-1",
            task_id="hermes-session-abc-turn-001",
            session_id="session-abc",
            observation_type="task.completed",
            payload={"result": "Something completed"},
        )
    )

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id)
    assert harvest_event is not None
    assert harvest_event.event_type == EventType.MEMORY_HARVEST_FAILED
    assert harvest_event.metadata["success"] is False

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 14: manual harvest API works
# ---------------------------------------------------------------------------


def test_manual_harvest_api_works(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    store.add(
        Observation(
            id="obs-1",
            task_id="hermes-session-abc-turn-001",
            session_id="session-abc",
            observation_type="task.completed",
            payload={"result": "Manual test"},
        )
    )

    result = coordinator.harvest_task("hermes-session-abc-turn-001")
    assert result is not None
    assert result["task_id"] == "hermes-session-abc-turn-001"
    assert "candidates" in result
    assert "observations_processed" in result

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 15: manual harvest is idempotent
# ---------------------------------------------------------------------------


def test_manual_harvest_is_idempotent(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    store.add(
        Observation(
            id="obs-1",
            task_id="hermes-session-abc-turn-001",
            session_id="session-abc",
            observation_type="task.completed",
            payload={"result": "Idempotent test"},
        )
    )

    result1 = coordinator.harvest_task("hermes-session-abc-turn-001")
    result2 = coordinator.harvest_task("hermes-session-abc-turn-001")

    assert result1 is not None
    assert result2 is not None
    assert result1["candidates"] == result2["candidates"]

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 16: no observation/memory cross-contamination between tasks
# ---------------------------------------------------------------------------


def test_no_cross_contamination_between_tasks(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    # Task A
    reg_a = AgentEvent(
        event_type=EventType.TASK_REGISTERED,
        metadata={"session_id": "s1", "task_id": "t1", "turn_id": "t1"},
    )
    coordinator._on_event(reg_a)
    comp_a = AgentEvent(
        event_type=EventType.TASK_COMPLETED,
        metadata={"session_id": "s1", "task_id": "t1", "turn_id": "t1"},
    )
    coordinator._on_event(comp_a)

    # Task B
    reg_b = AgentEvent(
        event_type=EventType.TASK_REGISTERED,
        metadata={"session_id": "s2", "task_id": "t2", "turn_id": "t2"},
    )
    coordinator._on_event(reg_b)
    comp_b = AgentEvent(
        event_type=EventType.TASK_COMPLETED,
        metadata={"session_id": "s2", "task_id": "t2", "turn_id": "t2"},
    )
    coordinator._on_event(comp_b)

    task_a_id = "hermes-s1-t1"
    task_b_id = "hermes-s2-t2"

    harvest_a = _wait_for_harvest(bus, task_a_id, timeout=3.0)
    harvest_b = _wait_for_harvest(bus, task_b_id, timeout=3.0)

    assert harvest_a is not None
    assert harvest_b is not None
    assert harvest_a.task_id == task_a_id
    assert harvest_b.task_id == task_b_id

    # Manual harvest should not cross-contaminate
    result_a = coordinator.harvest_task(task_a_id)
    result_b = coordinator.harvest_task(task_b_id)

    assert result_a is not None
    assert result_b is not None
    assert result_a["task_id"] == task_a_id
    assert result_b["task_id"] == task_b_id

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 17: coordinator without harvester still works
# ---------------------------------------------------------------------------


def test_coordinator_without_harvester_still_works(tmp_path):
    store = InMemoryObservationStore()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, None)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    time.sleep(0.2)

    # No harvest events should be emitted
    harvest_events = [
        e
        for e in bus.emitted
        if e.event_type
        in (
            EventType.MEMORY_HARVEST_COMPLETED,
            EventType.MEMORY_HARVEST_FAILED,
        )
    ]
    assert len(harvest_events) == 0

    # Manual harvest should return None
    result = coordinator.harvest_task("hermes-session-abc-turn-001")
    assert result is None

    coordinator.stop()


# ---------------------------------------------------------------------------
# Test 18: disabled harvesting works correctly
# ---------------------------------------------------------------------------


def test_disabled_harvesting_works():
    """When harvester is None (no memory_backend), no automatic harvesting."""
    store = InMemoryObservationStore()
    coordinator = DesktopTaskCoordinator(
        task_registry=None,
        persistence=None,
        event_bus=None,
        observation_store=store,
        memory_backend=None,
    )
    # Without event_bus, start should not crash
    coordinator.start()
    assert coordinator._harvester is None
    assert coordinator.harvest_task("any-task") is None


# ---------------------------------------------------------------------------
# Test 19: event ordering — observation available before harvest
# ---------------------------------------------------------------------------


def test_observation_available_before_harvest(tmp_path):
    store = InMemoryObservationStore()
    backend = InMemoryBackend()
    coordinator, _registry, _persistence, bus = _make_coordinator(tmp_path, store, backend)

    reg_event = _make_terminal_event(EventType.TASK_REGISTERED)
    coordinator._on_event(reg_event)

    complete_event = _make_terminal_event(EventType.TASK_COMPLETED)
    coordinator._on_event(complete_event)

    task_id = "hermes-session-abc-turn-001"
    harvest_event = _wait_for_harvest(bus, task_id, timeout=3.0)
    assert harvest_event is not None

    # The terminal observation should be in the store
    obs_list = store.list_by_task(task_id, limit=100)
    obs_types = [o["observation_type"] for o in obs_list]
    assert "task.completed" in obs_types

    coordinator.stop()
