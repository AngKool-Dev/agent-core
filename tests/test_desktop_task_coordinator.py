"""
Tests for DesktopTaskCoordinator.

Verifies:
* Idempotent task registration from TASK_REGISTERED events
* Correct identity mapping (Hermes execution → Argus task)
* State synchronization across lifecycle events
* Persistence of terminal states
* Multiple-turn and cross-session isolation
* Failure isolation
"""

from agentcore.desktop_task_coordinator import (
    DesktopTaskCoordinator,
)
from agentcore.events import AgentEvent, EventBus, EventType
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


def _event(
    metadata: dict, data: dict | None = None, event_type: EventType = EventType.TASK_REGISTERED
) -> AgentEvent:
    return AgentEvent(
        event_type=event_type,
        task_id="",
        data=data or {},
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Test 1: registration
# ---------------------------------------------------------------------------


def test_task_registered_creates_exactly_one_argus_task(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    event = _event(
        {
            "session_id": "session-abc",
            "task_id": "turn-001",
            "turn_id": "turn-001",
            "session_key": "20240101_120000_abc",
        }
    )
    coordinator.handle_event(event)

    tasks = registry.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].task_id == "hermes-session-abc-turn-001"
    assert tasks[0].task_state == TaskState.CREATED
    assert tasks[0].project == "hermes_desktop"


# ---------------------------------------------------------------------------
# Test 2: idempotency
# ---------------------------------------------------------------------------


def test_duplicate_task_registered_is_idempotent(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    event = _event(
        {
            "session_id": "session-abc",
            "task_id": "turn-001",
        }
    )

    coordinator.handle_event(event)
    coordinator.handle_event(event)

    tasks = registry.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].task_id == "hermes-session-abc-turn-001"


# ---------------------------------------------------------------------------
# Test 3: identity
# ---------------------------------------------------------------------------


def test_identity_maps_hermes_fields_to_argus_task(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)

    event = _event(
        {
            "session_id": "session-abc",
            "task_id": "turn-001",
            "turn_id": "turn-001",
            "session_key": "20240101_120000_abc",
        }
    )
    coordinator.handle_event(event)

    identity = coordinator.get_hermes_identity("hermes-session-abc-turn-001")
    assert identity is not None
    assert identity.hermes_session_id == "session-abc"
    assert identity.hermes_task_id == "turn-001"
    assert identity.hermes_turn_id == "turn-001"
    assert identity.hermes_session_key == "20240101_120000_abc"

    reverse = coordinator.get_task_for_hermes_execution("session-abc", "turn-001")
    assert reverse == "hermes-session-abc-turn-001"


# ---------------------------------------------------------------------------
# Test 4: state synchronization
# ---------------------------------------------------------------------------


def test_state_synchronization_lifecycle(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    sid, tid = "session-abc", "turn-001"

    coordinator.handle_event(_event({"session_id": sid, "task_id": tid}))
    coordinator.handle_event(
        _event({"session_id": sid, "task_id": tid}, event_type=EventType.TASK_STARTED)
    )
    coordinator.handle_event(
        _event({"session_id": sid, "task_id": tid}, event_type=EventType.TASK_COMPLETED)
    )

    record = registry.get("hermes-session-abc-turn-001")
    assert record is not None
    assert record.task_state == TaskState.COMPLETED


# ---------------------------------------------------------------------------
# Test 5: failure
# ---------------------------------------------------------------------------


def test_failure_event_sets_failed_state(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    sid, tid = "session-abc", "turn-001"
    coordinator.handle_event(_event({"session_id": sid, "task_id": tid}))

    fail_evt = AgentEvent(
        EventType.TASK_FAILED, task_id="", data={}, metadata={"session_id": sid, "task_id": tid}
    )
    coordinator.handle_event(fail_evt)

    record = registry.get("hermes-session-abc-turn-001")
    assert record.task_state == TaskState.FAILED


# ---------------------------------------------------------------------------
# Test 6: cancellation
# ---------------------------------------------------------------------------


def test_cancellation_event_sets_cancelled_state(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    sid, tid = "session-abc", "turn-001"
    coordinator.handle_event(_event({"session_id": sid, "task_id": tid}))

    cancel_evt = AgentEvent(
        EventType.TASK_CANCELLED, task_id="", data={}, metadata={"session_id": sid, "task_id": tid}
    )
    coordinator.handle_event(cancel_evt)

    record = registry.get("hermes-session-abc-turn-001")
    assert record.task_state == TaskState.CANCELLED


# ---------------------------------------------------------------------------
# Test 7: persistence
# ---------------------------------------------------------------------------


def test_terminal_state_persisted_and_reloadable(tmp_path):
    coordinator, _registry, persistence, _bus = _make_coordinator(tmp_path)

    sid, tid = "session-abc", "turn-001"
    coordinator.handle_event(_event({"session_id": sid, "task_id": tid}))

    complete_evt = AgentEvent(
        EventType.TASK_COMPLETED, task_id="", data={}, metadata={"session_id": sid, "task_id": tid}
    )
    coordinator.handle_event(complete_evt)

    loaded = persistence.load_task("hermes-session-abc-turn-001")
    assert loaded is not None
    assert loaded.current_state == TaskState.COMPLETED
    assert loaded.attributes["source"] == "hermes_desktop"
    assert loaded.attributes["hermes_session_id"] == "session-abc"
    assert loaded.attributes["hermes_task_id"] == "turn-001"


# ---------------------------------------------------------------------------
# Test 8: multiple turns
# ---------------------------------------------------------------------------


def test_multiple_turns_produce_separate_argus_tasks(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    sid = "session-abc"
    for turn in ["turn-001", "turn-002", "turn-003"]:
        event = _event({"session_id": sid, "task_id": turn, "turn_id": turn})
        coordinator.handle_event(event)

    tasks = registry.list_tasks()
    assert len(tasks) == 3
    task_ids = {t.task_id for t in tasks}
    assert task_ids == {
        "hermes-session-abc-turn-001",
        "hermes-session-abc-turn-002",
        "hermes-session-abc-turn-003",
    }


# ---------------------------------------------------------------------------
# Test 9: cross-session isolation
# ---------------------------------------------------------------------------


def test_cross_session_isolation(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    event_a = _event({"session_id": "session-a", "task_id": "turn-001"})
    event_b = _event({"session_id": "session-b", "task_id": "turn-001"})
    coordinator.handle_event(event_a)
    coordinator.handle_event(event_b)

    tasks = registry.list_tasks()
    assert len(tasks) == 2
    task_ids = {t.task_id for t in tasks}
    assert task_ids == {
        "hermes-session-a-turn-001",
        "hermes-session-b-turn-001",
    }


# ---------------------------------------------------------------------------
# Test 10: terminal event without prior registration
# ---------------------------------------------------------------------------


def test_terminal_event_without_registration_creates_task(tmp_path):
    """If TASK_COMPLETED arrives without a known registration, the coordinator
    auto-registers the task rather than silently dropping it.  This is the
    safest behavior because terminal events carry definitive state that should
    not be lost."""
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    sid, tid = "session-abc", "turn-001"
    complete_evt = AgentEvent(
        EventType.TASK_COMPLETED, task_id="", data={}, metadata={"session_id": sid, "task_id": tid}
    )
    coordinator.handle_event(complete_evt)

    tasks = registry.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].task_id == "hermes-session-abc-turn-001"
    assert tasks[0].task_state == TaskState.COMPLETED


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


def test_coordinator_failure_does_not_break_event_bus(tmp_path):
    """EventBus subscriber exceptions must not crash the bus."""
    coordinator, registry, _persistence, bus = _make_coordinator(tmp_path)

    class BadSubscriber:
        def __call__(self, event):
            raise RuntimeError("subscriber boom")

    bad = BadSubscriber()
    bus.subscribe(bad)

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    assert len(registry.list_tasks()) == 1


def test_coordinator_without_persistence_still_registers(tmp_path):
    """Coordinator works even when persistence is unavailable."""
    registry = TaskRegistry(persistence=None)
    bus = _CapturingBus()
    coordinator = DesktopTaskCoordinator(
        task_registry=registry,
        persistence=None,
        event_bus=bus,
    )
    coordinator.start()

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    assert len(registry.list_tasks()) == 1
    assert registry.list_tasks()[0].task_id == "hermes-session-abc-turn-001"


# ---------------------------------------------------------------------------
# Control tests
# ---------------------------------------------------------------------------


class FakeControlBridge:
    """Fake Hermes control bridge for testing."""

    def __init__(self, sessions: dict[str, dict] | None = None) -> None:
        self._sessions = sessions or {}
        self.cancel_calls: list[tuple[str, dict]] = []

    def get_status(self, session_id: str) -> dict:
        return self._sessions.get(
            session_id,
            {
                "status": "not_found",
                "running": False,
                "cancel_requested": False,
                "agent_present": False,
            },
        )

    def cancel(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)
        if session is None:
            return {"accepted": False, "message": "not found", "hermes_status": "not_found"}
        if session.get("cancel_requested"):
            return {"accepted": True, "message": "already cancelling", "hermes_status": "cancelled"}
        if not session.get("running"):
            return {"accepted": False, "message": "idle", "hermes_status": "idle"}
        self.cancel_calls.append((session_id, session))
        session["cancel_requested"] = True
        return {"accepted": True, "message": "cancelled", "hermes_status": "active"}


def test_query_status_returns_accepted_for_active_task(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    bridge = FakeControlBridge(
        {
            "session-abc": {
                "status": "active",
                "running": True,
                "cancel_requested": False,
                "agent_present": True,
            },
        }
    )
    coordinator._control_bridge = bridge

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    result = coordinator.query_status("hermes-session-abc-turn-001")
    assert result.accepted is True
    assert result.hermes_status == "active"
    assert result.argus_task_id == "hermes-session-abc-turn-001"


def test_query_status_returns_not_found_for_unknown_task():
    registry = TaskRegistry(persistence=None)
    bus = _CapturingBus()
    coordinator = DesktopTaskCoordinator(
        task_registry=registry,
        persistence=None,
        event_bus=bus,
        control_bridge=FakeControlBridge(),
    )

    result = coordinator.query_status("nonexistent-task")
    assert result.not_found is True
    assert result.argus_task_id == "nonexistent-task"


def test_query_status_returns_completed_already_for_terminal_task(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    bridge = FakeControlBridge(
        {
            "session-abc": {
                "status": "idle",
                "running": False,
                "cancel_requested": False,
                "agent_present": True,
            },
        }
    )
    coordinator._control_bridge = bridge

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    complete_evt = AgentEvent(
        EventType.TASK_COMPLETED,
        task_id="",
        data={},
        metadata={"session_id": "session-abc", "task_id": "turn-001"},
    )
    coordinator.handle_event(complete_evt)

    result = coordinator.query_status("hermes-session-abc-turn-001")
    assert result.completed_already is True
    assert result.argus_task_id == "hermes-session-abc-turn-001"


def test_request_cancel_delegates_to_bridge(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    bridge = FakeControlBridge(
        {
            "session-abc": {
                "status": "active",
                "running": True,
                "cancel_requested": False,
                "agent_present": True,
            },
        }
    )
    coordinator._control_bridge = bridge

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    result = coordinator.request_cancel("hermes-session-abc-turn-001")
    assert result.accepted is True
    assert result.message == "cancelled"
    assert len(bridge.cancel_calls) == 1
    assert bridge.cancel_calls[0][0] == "session-abc"


def test_duplicate_cancel_is_idempotent(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    bridge = FakeControlBridge(
        {
            "session-abc": {
                "status": "active",
                "running": True,
                "cancel_requested": False,
                "agent_present": True,
            },
        }
    )
    coordinator._control_bridge = bridge

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    result1 = coordinator.request_cancel("hermes-session-abc-turn-001")
    result2 = coordinator.request_cancel("hermes-session-abc-turn-001")

    assert result1.accepted is True
    assert result2.accepted is True
    assert len(bridge.cancel_calls) == 1


def test_cancel_unknown_task_returns_not_found():
    registry = TaskRegistry(persistence=None)
    bus = _CapturingBus()
    coordinator = DesktopTaskCoordinator(
        task_registry=registry,
        persistence=None,
        event_bus=bus,
        control_bridge=FakeControlBridge(),
    )

    result = coordinator.request_cancel("nonexistent-task")
    assert result.not_found is True


def test_cancel_after_completion_returns_completed_already(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    bridge = FakeControlBridge(
        {
            "session-abc": {
                "status": "idle",
                "running": False,
                "cancel_requested": False,
                "agent_present": True,
            },
        }
    )
    coordinator._control_bridge = bridge

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    complete_evt = AgentEvent(
        EventType.TASK_COMPLETED,
        task_id="",
        data={},
        metadata={"session_id": "session-abc", "task_id": "turn-001"},
    )
    coordinator.handle_event(complete_evt)

    result = coordinator.request_cancel("hermes-session-abc-turn-001")
    assert result.completed_already is True


def test_control_bridge_failure_does_not_corrupt_registry(tmp_path):
    coordinator, registry, _persistence, _bus = _make_coordinator(tmp_path)

    class BadBridge:
        def get_status(self, session_id):
            raise RuntimeError("bridge down")

        def cancel(self, session_id):
            raise RuntimeError("bridge down")

    coordinator._control_bridge = BadBridge()

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    result = coordinator.request_cancel("hermes-session-abc-turn-001")
    assert result.failed is True
    assert len(registry.list_tasks()) == 1


def test_cancel_uses_explicit_identity_not_prompt_text(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    bridge = FakeControlBridge(
        {
            "session-abc": {
                "status": "active",
                "running": True,
                "cancel_requested": False,
                "agent_present": True,
            },
        }
    )
    coordinator._control_bridge = bridge

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    result = coordinator.request_cancel("hermes-session-abc-turn-001")
    assert result.accepted is True
    assert bridge.cancel_calls[0][0] == "session-abc"


def test_query_status_without_bridge_returns_not_found(tmp_path):
    coordinator, _registry, _persistence, _bus = _make_coordinator(tmp_path)
    coordinator._control_bridge = None

    event = _event({"session_id": "session-abc", "task_id": "turn-001"})
    coordinator.handle_event(event)

    result = coordinator.query_status("hermes-session-abc-turn-001")
    assert result.not_found is True
    assert result.message == "control bridge not available"
