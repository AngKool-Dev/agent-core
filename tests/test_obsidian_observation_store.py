"""
Tests for DBObsidianObservationStore.

Verifies:
* Persistence roundtrip (save → reload)
* Restart recovery (destroy store A, create store B, verify data)
* ID preservation (observation.id survives persistence)
* Sequence preservation
* Duplicate observation behavior (idempotent via dedupe)
* Task filtering
* Session filtering
* Empty store behavior
* Concurrent writes
* Malformed observation handling
* Backend failure isolation
* Coordinator + persistent observation integration
"""

import os
import tempfile
import threading
import time
import uuid

import pytest

try:
    import db_obsidian

    _DBO_SCHEMA_OK = db_obsidian.SCHEMA_FILE.exists()
except (ImportError, AttributeError):
    _DBO_SCHEMA_OK = False

if not _DBO_SCHEMA_OK:
    pytest.skip(
        "db-obsidian not available or schema missing; "
        "install with: pip install git+https://github.com/AngKool-Dev/db-obsidian",
        allow_module_level=True,
    )

from agentcore.adapters.obsidian_observation_store import DBObsidianObservationStore
from agentcore.desktop_task_coordinator import DesktopTaskCoordinator
from agentcore.events import AgentEvent, EventBus, EventType
from agentcore.observations import (
    Observation,
    ObservationCollector,
    ObservationType,
)
from agentcore.persistence import (
    FilesystemPersistenceBackend,
    InMemoryEventStore,
    TaskPersistenceManager,
)
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


def _make_coordinator(tmp_path):
    backend = FilesystemPersistenceBackend(str(tmp_path / "tasks"))
    event_store = InMemoryEventStore()
    persistence = TaskPersistenceManager(backend=backend, event_store=event_store)
    registry = TaskRegistry(persistence=persistence)
    bus = _CapturingBus()
    coordinator = DesktopTaskCoordinator(
        task_registry=registry,
        persistence=persistence,
        event_bus=bus,
    )
    coordinator.start()
    return coordinator, registry, persistence, bus


def _make_observation(
    observation_id=None,
    task_id="t1",
    session_id="s1",
    turn_id="turn-1",
    observation_type=ObservationType.TASK_REGISTERED.value,
    payload=None,
    metadata=None,
    sequence=1,
):
    return Observation(
        id=observation_id or f"obs-{uuid.uuid4().hex[:12]}",
        task_id=task_id,
        session_id=session_id,
        turn_id=turn_id,
        observation_type=observation_type,
        payload=payload or {},
        metadata=metadata or {},
        sequence=sequence,
    )


def _make_db_store():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return DBObsidianObservationStore(db_path), db_path


def _safe_unlink(path, retries=5, delay=0.1):
    """Safely delete a file, retrying on Windows if it's still locked."""
    for _ in range(retries):
        try:
            os.unlink(path)
            return
        except PermissionError:
            time.sleep(delay)
    try:
        os.unlink(path)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: persistence roundtrip
# ---------------------------------------------------------------------------


def test_persistence_roundtrip_preserves_all_fields():
    store, db_path = _make_db_store()
    try:
        obs = _make_observation(
            task_id="task-1",
            session_id="session-1",
            turn_id="turn-1",
            observation_type=ObservationType.TOOL_CALL_STARTED.value,
            payload={"name": "terminal", "args": {"command": "pwd"}},
            metadata={"tool_call_id": "tc-1", "model_request_id": "req-1"},
            sequence=42,
        )
        store.add(obs)

        loaded = store.get(obs.id)
        assert loaded is not None
        assert loaded["id"] == obs.id
        assert loaded["task_id"] == "task-1"
        assert loaded["session_id"] == "session-1"
        assert loaded["turn_id"] == "turn-1"
        assert loaded["observation_type"] == ObservationType.TOOL_CALL_STARTED.value
        assert loaded["payload"]["name"] == "terminal"
        assert loaded["metadata"]["tool_call_id"] == "tc-1"
        assert loaded["sequence"] == 42
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 2: restart recovery
# ---------------------------------------------------------------------------


def test_restart_recovery_preserves_observations():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        store_a = DBObsidianObservationStore(db_path)
        obs1 = _make_observation(
            task_id="task-1", session_id="s1", observation_type=ObservationType.TASK_STARTED.value
        )
        obs2 = _make_observation(
            task_id="task-1", session_id="s1", observation_type=ObservationType.TASK_COMPLETED.value
        )
        store_a.add(obs1)
        store_a.add(obs2)
        store_a.close()

        store_b = DBObsidianObservationStore(db_path)
        loaded1 = store_b.get(obs1.id)
        loaded2 = store_b.get(obs2.id)
        assert loaded1 is not None
        assert loaded2 is not None
        assert loaded1["observation_type"] == ObservationType.TASK_STARTED.value
        assert loaded2["observation_type"] == ObservationType.TASK_COMPLETED.value
        store_b.close()
    finally:
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 3: ID preservation
# ---------------------------------------------------------------------------


def test_id_preserved_after_persistence():
    store, db_path = _make_db_store()
    try:
        obs = _make_observation(observation_id="fixed-id-1")
        store.add(obs)
        loaded = store.get("fixed-id-1")
        assert loaded is not None
        assert loaded["id"] == "fixed-id-1"
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 4: sequence preservation
# ---------------------------------------------------------------------------


def test_sequence_preserved_after_persistence():
    store, db_path = _make_db_store()
    try:
        obs1 = _make_observation(sequence=1)
        time.sleep(0.01)
        obs2 = _make_observation(sequence=2)
        time.sleep(0.01)
        obs3 = _make_observation(sequence=3)
        store.add(obs1)
        store.add(obs2)
        store.add(obs3)

        task_obs = store.list_by_task("t1", limit=10)
        sequences = sorted([o["sequence"] for o in task_obs])
        assert sequences == [1, 2, 3]
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 5: duplicate observation behavior
# ---------------------------------------------------------------------------


def test_duplicate_observation_is_idempotent():
    store, db_path = _make_db_store()
    try:
        obs = _make_observation(observation_id="dup-id")
        store.add(obs)
        store.add(obs)
        store.add(obs)

        task_obs = store.list_by_task("t1", limit=10)
        assert len(task_obs) == 1
        assert task_obs[0]["id"] == "dup-id"
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 6: task filtering
# ---------------------------------------------------------------------------


def test_task_filtering_returns_only_matching_observations():
    store, db_path = _make_db_store()
    try:
        store.add(
            _make_observation(task_id="task-a", observation_type=ObservationType.TASK_STARTED.value)
        )
        store.add(
            _make_observation(
                task_id="task-a", observation_type=ObservationType.TASK_COMPLETED.value
            )
        )
        store.add(
            _make_observation(task_id="task-b", observation_type=ObservationType.TASK_STARTED.value)
        )

        task_a_obs = store.list_by_task("task-a", limit=10)
        assert len(task_a_obs) == 2
        assert all(o["task_id"] == "task-a" for o in task_a_obs)

        task_b_obs = store.list_by_task("task-b", limit=10)
        assert len(task_b_obs) == 1
        assert task_b_obs[0]["observation_type"] == ObservationType.TASK_STARTED.value
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 7: session filtering
# ---------------------------------------------------------------------------


def test_session_filtering_returns_only_matching_observations():
    store, db_path = _make_db_store()
    try:
        store.add(
            _make_observation(
                session_id="session-x", observation_type=ObservationType.TASK_STARTED.value
            )
        )
        store.add(
            _make_observation(
                session_id="session-x", observation_type=ObservationType.TASK_COMPLETED.value
            )
        )
        store.add(
            _make_observation(
                session_id="session-y", observation_type=ObservationType.TASK_STARTED.value
            )
        )

        session_x_obs = store.list_by_session("session-x", limit=10)
        assert len(session_x_obs) == 2
        assert all(o["session_id"] == "session-x" for o in session_x_obs)

        session_y_obs = store.list_by_session("session-y", limit=10)
        assert len(session_y_obs) == 1
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 8: empty store
# ---------------------------------------------------------------------------


def test_empty_store_returns_empty_results():
    store, db_path = _make_db_store()
    try:
        assert store.get("nonexistent") is None
        assert store.list_by_task("nonexistent") == []
        assert store.list_by_session("nonexistent") == []
        assert store.clear("nonexistent") == 0
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 9: concurrent writes
# ---------------------------------------------------------------------------


def test_concurrent_writes_are_safe():
    store, db_path = _make_db_store()
    try:
        errors = []

        def writer(tid):
            try:
                for i in range(10):
                    obs = _make_observation(
                        task_id=f"task-{tid}",
                        session_id=f"session-{tid}",
                        observation_type=ObservationType.TASK_STARTED.value,
                        sequence=i,
                    )
                    store.add(obs)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        for i in range(5):
            task_obs = store.list_by_task(f"task-{i}", limit=20)
            assert len(task_obs) == 10
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 10: malformed observation handling
# ---------------------------------------------------------------------------


def test_malformed_observation_does_not_corrupt_store():
    store, db_path = _make_db_store()
    try:
        good_obs = _make_observation(observation_type=ObservationType.TASK_STARTED.value)
        store.add(good_obs)

        bad_obs = Observation(
            id="bad-obs",
            task_id="",
            session_id="",
            observation_type="",
            payload={},
            metadata={},
            sequence=0,
        )
        store.add(bad_obs)

        all_obs = store.list_by_task("t1", limit=10)
        assert len(all_obs) >= 1
        assert all_obs[0]["id"] == good_obs.id
    finally:
        store.close()
        _safe_unlink(db_path)


# ---------------------------------------------------------------------------
# Test 11: backend failure isolation
# ---------------------------------------------------------------------------


def test_backend_failure_does_not_break_coordinator(tmp_path):
    """Observation store failure must not break DesktopTaskCoordinator."""
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    class BadStore:
        def add(self, obs):
            raise RuntimeError("db dead")

        def get(self, oid):
            return None

        def list_by_task(self, task_id, limit=1000):
            return []

        def list_by_session(self, session_id, limit=1000):
            return []

        def clear(self, task_id):
            return 0

    coordinator._observation_collector = ObservationCollector(store=BadStore())

    event = AgentEvent(
        event_type=EventType.TASK_REGISTERED,
        metadata={"session_id": "session-abc", "task_id": "turn-001"},
    )
    coordinator._on_event(event)

    assert len(registry.list_tasks()) == 1


# ---------------------------------------------------------------------------
# Test 12: coordinator + persistent observation integration
# ---------------------------------------------------------------------------


def test_coordinator_with_db_obsidian_store(tmp_path):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        backend = FilesystemPersistenceBackend(str(tmp_path / "tasks"))
        event_store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=event_store)
        registry = TaskRegistry(persistence=persistence)
        bus = EventBus()

        obs_store = DBObsidianObservationStore(db_path)
        coordinator = DesktopTaskCoordinator(
            task_registry=registry,
            persistence=persistence,
            event_bus=bus,
            observation_store=obs_store,
        )
        coordinator.start()

        event = AgentEvent(
            event_type=EventType.TASK_REGISTERED,
            metadata={"session_id": "session-abc", "task_id": "turn-001", "turn_id": "turn-001"},
        )
        coordinator._on_event(event)

        observations = coordinator._observation_collector.get_observations(
            "hermes-session-abc-turn-001"
        )
        assert len(observations) >= 1
        assert observations[0]["observation_type"] == ObservationType.TASK_REGISTERED.value
        assert observations[0]["task_id"] == "hermes-session-abc-turn-001"

        # Restart recovery
        obs_store.close()
        obs_store2 = DBObsidianObservationStore(db_path)
        loaded = obs_store2.get(observations[0]["id"])
        assert loaded is not None
        assert loaded["observation_type"] == ObservationType.TASK_REGISTERED.value
        obs_store2.close()
    finally:
        _safe_unlink(db_path)
