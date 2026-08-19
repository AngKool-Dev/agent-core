"""
Tests for the Observation layer (Phase 5A).

Verifies:
* Observation creation from EventBus events
* Correlation identifiers (task_id, session_id, turn_id, tool_call_id, model_request_id)
* Sequence ordering
* Missing and duplicate event handling
* Orphan completion handling
* Multiple turns and tool calls
* Terminal task observations
* ObservationStore persistence
* ObservationCollector integration with DesktopTaskCoordinator
"""

import uuid

from agentcore.desktop_task_coordinator import DesktopTaskCoordinator
from agentcore.events import AgentEvent, EventBus, EventType
from agentcore.observations import (
    InMemoryObservationStore,
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


def _make_observation(event_type, metadata=None, data=None, event_id=None):
    return AgentEvent(
        event_type=event_type,
        task_id="",
        data=data or {},
        metadata=metadata or {},
        id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
    )


# ---------------------------------------------------------------------------
# Test 1: observation creation from events
# ---------------------------------------------------------------------------


def test_observation_created_from_lifecycle_event():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    event = _make_observation(
        EventType.TASK_REGISTERED,
        metadata={"session_id": "s1", "task_id": "t1", "turn_id": "turn-1"},
    )
    obs = collector.handle_event(event)

    assert obs is not None
    assert obs["observation_type"] == ObservationType.TASK_REGISTERED.value
    assert obs["task_id"] == "t1"
    assert obs["session_id"] == "s1"
    assert obs["turn_id"] == "turn-1"


def test_observation_created_from_tool_event():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    event = _make_observation(
        EventType.TOOL_CALL_STARTED,
        metadata={
            "session_id": "s1",
            "task_id": "t1",
            "tool_id": "tc-1",
        },
        data={"name": "terminal", "args": {"command": "pwd"}},
    )
    obs = collector.handle_event(event)

    assert obs is not None
    assert obs["observation_type"] == ObservationType.TOOL_CALL_STARTED.value
    assert obs["tool_call_id"] == "tc-1"
    assert obs["payload"]["name"] == "terminal"


def test_observation_created_from_model_event():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    event = _make_observation(
        EventType.MODEL_REQUEST_STARTED,
        metadata={"session_id": "s1", "task_id": "t1", "model": "gpt-4"},
    )
    obs = collector.handle_event(event)

    assert obs is not None
    assert obs["observation_type"] == ObservationType.MODEL_REQUEST_STARTED.value
    assert obs["model_request_id"] != ""
    assert obs["metadata"]["model"] == "gpt-4"


def test_unknown_event_returns_none():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    class FakeEventType:
        value = "fake.event"

    event = _make_observation(FakeEventType(), metadata={"session_id": "s1"})
    obs = collector.handle_event(event)
    assert obs is None


# ---------------------------------------------------------------------------
# Test 2: correlation identifiers
# ---------------------------------------------------------------------------


def test_model_request_response_share_correlation_id():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    req_event = _make_observation(
        EventType.MODEL_REQUEST_STARTED,
        metadata={"session_id": "s1", "task_id": "t1"},
    )
    req_obs = collector.handle_event(req_event)
    model_request_id = req_obs["model_request_id"]
    assert model_request_id != ""

    resp_event = _make_observation(
        EventType.MODEL_RESPONSE_RECEIVED,
        metadata={
            "session_id": "s1",
            "task_id": "t1",
            "model_request_id": model_request_id,
        },
    )
    resp_obs = collector.handle_event(resp_event)
    assert resp_obs is not None
    assert resp_obs["model_request_id"] == model_request_id


def test_tool_call_start_complete_share_correlation_id():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    tc_id = "tc-42"
    start_event = _make_observation(
        EventType.TOOL_CALL_STARTED,
        metadata={"session_id": "s1", "task_id": "t1", "tool_id": tc_id},
    )
    start_obs = collector.handle_event(start_event)
    assert start_obs["tool_call_id"] == tc_id

    complete_event = _make_observation(
        EventType.TOOL_CALL_COMPLETED,
        metadata={"session_id": "s1", "task_id": "t1", "tool_id": tc_id},
    )
    complete_obs = collector.handle_event(complete_event)
    assert complete_obs["tool_call_id"] == tc_id


def test_sequence_numbers_are_monotonic():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    events = [
        _make_observation(
            EventType.TASK_REGISTERED, metadata={"session_id": "s1", "task_id": "t1"}
        ),
        _make_observation(EventType.TASK_STARTED, metadata={"session_id": "s1", "task_id": "t1"}),
        _make_observation(
            EventType.TOOL_CALL_STARTED,
            metadata={"session_id": "s1", "task_id": "t1", "tool_id": "tc-1"},
        ),
        _make_observation(
            EventType.TOOL_CALL_COMPLETED,
            metadata={"session_id": "s1", "task_id": "t1", "tool_id": "tc-1"},
        ),
        _make_observation(EventType.TASK_COMPLETED, metadata={"session_id": "s1", "task_id": "t1"}),
    ]

    observations = [collector.handle_event(e) for e in events]
    sequences = [obs["sequence"] for obs in observations if obs]
    assert sequences == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Test 3: missing events
# ---------------------------------------------------------------------------


def test_missing_model_response_does_not_break_collector():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    req_event = _make_observation(
        EventType.MODEL_REQUEST_STARTED,
        metadata={"session_id": "s1", "task_id": "t1"},
    )
    req_obs = collector.handle_event(req_event)
    assert req_obs is not None

    observations = store.list_by_task("t1")
    assert len(observations) == 1


def test_orphan_tool_completion_is_recorded():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    complete_event = _make_observation(
        EventType.TOOL_CALL_COMPLETED,
        metadata={"session_id": "s1", "task_id": "t1", "tool_id": "tc-99"},
    )
    obs = collector.handle_event(complete_event)
    assert obs is not None
    assert obs["tool_call_id"] == "tc-99"
    assert obs["observation_type"] == ObservationType.TOOL_CALL_COMPLETED.value


# ---------------------------------------------------------------------------
# Test 4: duplicate events
# ---------------------------------------------------------------------------


def test_duplicate_events_produce_separate_observations():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    event = _make_observation(
        EventType.TASK_STARTED,
        metadata={"session_id": "s1", "task_id": "t1"},
    )
    obs1 = collector.handle_event(event)
    obs2 = collector.handle_event(event)

    assert obs1 is not None
    assert obs2 is not None
    assert obs1["id"] != obs2["id"]
    assert obs1["sequence"] == 1
    assert obs2["sequence"] == 2


# ---------------------------------------------------------------------------
# Test 5: multiple turns
# ---------------------------------------------------------------------------


def test_multiple_turns_produce_separate_observation_streams(tmp_path):
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    turns = ["turn-001", "turn-002", "turn-003"]
    for turn in turns:
        collector.handle_event(
            _make_observation(
                EventType.TASK_REGISTERED,
                metadata={"session_id": "s1", "task_id": turn, "turn_id": turn},
            )
        )
        collector.handle_event(
            _make_observation(
                EventType.TASK_STARTED,
                metadata={"session_id": "s1", "task_id": turn, "turn_id": turn},
            )
        )
        collector.handle_event(
            _make_observation(
                EventType.TASK_COMPLETED,
                metadata={"session_id": "s1", "task_id": turn, "turn_id": turn},
            )
        )

    all_observations = store.list_by_session("s1", limit=100)
    assert len(all_observations) == 9

    for turn in turns:
        turn_obs = store.list_by_task(turn, limit=10)
        assert len(turn_obs) == 3


# ---------------------------------------------------------------------------
# Test 6: multiple tool calls
# ---------------------------------------------------------------------------


def test_multiple_tool_calls_correlated_correctly():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    tool_calls = [
        ("tc-1", "terminal", {"command": "pwd"}),
        ("tc-2", "read_file", {"path": "/tmp/x"}),
        ("tc-3", "write_file", {"path": "/tmp/y", "content": "z"}),
    ]

    for tc_id, name, args in tool_calls:
        collector.handle_event(
            _make_observation(
                EventType.TOOL_CALL_STARTED,
                metadata={"session_id": "s1", "task_id": "t1", "tool_id": tc_id},
                data={"name": name, "args": args},
            )
        )
        collector.handle_event(
            _make_observation(
                EventType.TOOL_CALL_COMPLETED,
                metadata={"session_id": "s1", "task_id": "t1", "tool_id": tc_id},
                data={"name": name, "result": "ok"},
            )
        )

    task_obs = store.list_by_task("t1", limit=20)
    assert len(task_obs) == 6

    tool_starts = [
        o for o in task_obs if o["observation_type"] == ObservationType.TOOL_CALL_STARTED.value
    ]
    tool_completes = [
        o for o in task_obs if o["observation_type"] == ObservationType.TOOL_CALL_COMPLETED.value
    ]
    assert len(tool_starts) == 3
    assert len(tool_completes) == 3
    assert [o["tool_call_id"] for o in tool_starts] == ["tc-1", "tc-2", "tc-3"]
    assert [o["tool_call_id"] for o in tool_completes] == ["tc-1", "tc-2", "tc-3"]


# ---------------------------------------------------------------------------
# Test 7: terminal task observations
# ---------------------------------------------------------------------------


def test_terminal_task_produces_completion_observation():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    collector.handle_event(
        _make_observation(
            EventType.TASK_REGISTERED,
            metadata={"session_id": "s1", "task_id": "t1"},
        )
    )
    collector.handle_event(
        _make_observation(
            EventType.TASK_STARTED,
            metadata={"session_id": "s1", "task_id": "t1"},
        )
    )
    collector.handle_event(
        _make_observation(
            EventType.TASK_COMPLETED,
            metadata={"session_id": "s1", "task_id": "t1"},
        )
    )

    task_obs = store.list_by_task("t1", limit=10)
    types = [o["observation_type"] for o in task_obs]
    assert ObservationType.TASK_COMPLETED.value in types
    assert all(o["task_id"] == "t1" for o in task_obs)


# ---------------------------------------------------------------------------
# Test 8: observation store persistence
# ---------------------------------------------------------------------------


def test_observation_store_persists_and_clears(tmp_path):
    FilesystemPersistenceBackend(str(tmp_path / "obs"))
    store = InMemoryObservationStore()

    obs = Observation(
        task_id="t1",
        session_id="s1",
        turn_id="turn-1",
        observation_type=ObservationType.TASK_COMPLETED.value,
        payload={"result": "ok"},
    )
    store.add(obs)

    task_obs = store.list_by_task("t1", limit=10)
    assert len(task_obs) == 1
    assert task_obs[0]["id"] == obs.id

    cleared = store.clear("t1")
    assert cleared == 1
    assert len(store.list_by_task("t1", limit=10)) == 0


# ---------------------------------------------------------------------------
# Test 9: observation collector with desktop task coordinator
# ---------------------------------------------------------------------------


def test_desktop_coordinator_produces_observations(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)

    event = _make_observation(
        EventType.TASK_REGISTERED,
        metadata={"session_id": "session-abc", "task_id": "turn-001", "turn_id": "turn-001"},
    )
    coordinator._on_event(event)

    observations = coordinator._observation_collector.get_observations(
        "hermes-session-abc-turn-001"
    )
    assert len(observations) >= 1
    assert observations[0]["observation_type"] == ObservationType.TASK_REGISTERED.value
    assert observations[0]["task_id"] == "hermes-session-abc-turn-001"


def test_observation_collector_failure_does_not_break_coordinator(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    class BadStore:
        def add(self, obs):
            raise RuntimeError("store dead")

        def get(self, oid):
            return None

        def list_by_task(self, task_id, limit=1000):
            return []

        def list_by_session(self, session_id, limit=1000):
            return []

        def clear(self, task_id):
            return 0

    coordinator._observation_collector = ObservationCollector(store=BadStore())

    event = _make_observation(
        EventType.TASK_REGISTERED,
        metadata={"session_id": "session-abc", "task_id": "turn-001"},
    )
    coordinator._on_event(event)

    assert len(registry.list_tasks()) == 1


# ---------------------------------------------------------------------------
# Test 10: cross-session isolation
# ---------------------------------------------------------------------------


def test_cross_session_observations_are_isolated():
    store = InMemoryObservationStore()
    collector = ObservationCollector(store=store)
    collector.start()

    for session in ["session-a", "session-b"]:
        for turn in ["turn-1", "turn-2"]:
            collector.handle_event(
                _make_observation(
                    EventType.TASK_REGISTERED,
                    metadata={"session_id": session, "task_id": turn, "turn_id": turn},
                )
            )
            collector.handle_event(
                _make_observation(
                    EventType.TASK_STARTED,
                    metadata={"session_id": session, "task_id": turn, "turn_id": turn},
                )
            )

    session_a_obs = store.list_by_session("session-a", limit=100)
    session_b_obs = store.list_by_session("session-b", limit=100)
    assert len(session_a_obs) == 4
    assert len(session_b_obs) == 4
    assert all(o["session_id"] == "session-a" for o in session_a_obs)
    assert all(o["session_id"] == "session-b" for o in session_b_obs)
