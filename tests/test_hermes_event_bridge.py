"""
Tests for HermesEventBridge — the Hermes Desktop → Argus observation bridge.

These tests verify:
* Event translation (Hermes event name → Argus EventType)
* Identity preservation (session_id → task_id correlation)
* Failure isolation (bridge exceptions do not propagate)
* Completion / failure / cancellation mapping
* EventBus absence handling
"""

from typing import Any

from agentcore.adapters.hermes_event_bridge import _EVENT_MAP, HermesEventBridge
from agentcore.events import EventBus, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CapturingBus:
    """Minimal EventBus stand-in that captures emitted events for assertions."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.subscriber_count = 1

    def emit(self, event) -> None:
        self.events.append(
            {
                "event_type": event.event_type,
                "task_id": event.task_id,
                "data": dict(event.data),
                "metadata": dict(event.metadata),
            }
        )

    def subscribe(self, callback) -> None:
        pass

    def unsubscribe(self, callback) -> None:
        pass


# ---------------------------------------------------------------------------
# Event mapping tests
# ---------------------------------------------------------------------------


class TestEventMapping:
    """Hermes event names must map to the correct Argus EventType."""

    def test_session_start_maps_to_task_registered(self):
        assert _EVENT_MAP["on_session_start"] == EventType.TASK_REGISTERED

    def test_session_end_maps_to_task_completed(self):
        assert _EVENT_MAP["on_session_end"] == EventType.TASK_COMPLETED

    def test_session_finalize_maps_to_task_state_changed(self):
        assert _EVENT_MAP["on_session_finalize"] == EventType.TASK_STATE_CHANGED

    def test_session_reset_maps_to_task_state_changed(self):
        assert _EVENT_MAP["on_session_reset"] == EventType.TASK_STATE_CHANGED

    def test_pre_llm_call_maps_to_model_request_started(self):
        assert _EVENT_MAP["pre_llm_call"] == EventType.MODEL_REQUEST_STARTED

    def test_pre_api_request_maps_to_model_request_started(self):
        assert _EVENT_MAP["pre_api_request"] == EventType.MODEL_REQUEST_STARTED

    def test_pre_tool_call_maps_to_tool_call_started(self):
        assert _EVENT_MAP["pre_tool_call"] == EventType.TOOL_CALL_STARTED

    def test_post_tool_call_maps_to_tool_call_completed(self):
        assert _EVENT_MAP["post_tool_call"] == EventType.TOOL_CALL_COMPLETED

    def test_post_approval_response_maps_to_tool_call_completed(self):
        assert _EVENT_MAP["post_approval_response"] == EventType.TOOL_CALL_COMPLETED

    def test_post_api_request_maps_to_model_response_received(self):
        assert _EVENT_MAP["post_api_request"] == EventType.MODEL_RESPONSE_RECEIVED

    def test_api_request_error_maps_to_model_error(self):
        assert _EVENT_MAP["api_request_error"] == EventType.MODEL_ERROR

    def test_on_skill_lifecycle_maps_to_skill_loaded(self):
        assert _EVENT_MAP["on_skill_lifecycle"] == EventType.SKILL_LOADED

    def test_subagent_stop_maps_to_task_completed(self):
        assert _EVENT_MAP["subagent_stop"] == EventType.TASK_COMPLETED

    def test_tool_started_maps_to_tool_call_started(self):
        assert _EVENT_MAP["tool.started"] == EventType.TOOL_CALL_STARTED

    def test_tool_completed_maps_to_tool_call_completed(self):
        assert _EVENT_MAP["tool.completed"] == EventType.TOOL_CALL_COMPLETED

    def test_session_compress_maps_to_task_state_changed(self):
        assert _EVENT_MAP["session:compress"] == EventType.TASK_STATE_CHANGED

    def test_execution_start_maps_to_task_started(self):
        assert _EVENT_MAP["execution:start"] == EventType.TASK_STARTED

    def test_execution_complete_maps_to_task_completed(self):
        assert _EVENT_MAP["execution:complete"] == EventType.TASK_COMPLETED

    def test_execution_failed_maps_to_task_failed(self):
        assert _EVENT_MAP["execution:failed"] == EventType.TASK_FAILED

    def test_execution_cancelled_maps_to_task_cancelled(self):
        assert _EVENT_MAP["execution:cancelled"] == EventType.TASK_CANCELLED


# ---------------------------------------------------------------------------
# Bridge behaviour tests
# ---------------------------------------------------------------------------


class TestHermesEventBridge:
    """HermesEventBridge translates and emits events correctly."""

    def test_emit_translates_event_type(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="sess-abc", task_id="task-1")
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_REGISTERED

    def test_emit_uses_session_id_as_task_id_fallback(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="sess-abc")
        assert bus.events[0]["task_id"] == "sess-abc"

    def test_emit_uses_explicit_task_id_when_provided(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "on_session_start",
            session_id="sess-abc",
            task_id="task-explicit",
        )
        assert bus.events[0]["task_id"] == "task-explicit"

    def test_emit_carries_metadata(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "tool.started",
            session_id="sess-abc",
            task_id="task-1",
            metadata={"tool_name": "read_file", "args": {"path": "x.py"}},
        )
        assert bus.events[0]["data"]["tool_name"] == "read_file"
        assert bus.events[0]["data"]["args"] == {"path": "x.py"}

    def test_emit_is_noop_when_event_bus_is_none(self):
        bridge = HermesEventBridge(event_bus=None)
        bridge.emit("on_session_start", session_id="sess-abc")  # must not raise

    def test_emit_is_noop_when_event_bus_has_no_subscribers(self):
        bus = EventBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="sess-abc")  # must not raise

    def test_emit_is_noop_for_unknown_event_name(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("nonexistent.event", session_id="sess-abc")
        assert len(bus.events) == 0

    def test_disable_prevents_emission(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.disable()
        bridge.emit("on_session_start", session_id="sess-abc")
        assert len(bus.events) == 0

    def test_enable_restores_emission(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.disable()
        bridge.enable()
        bridge.emit("on_session_start", session_id="sess-abc")
        assert len(bus.events) == 1

    def test_event_bus_setter(self):
        bus1 = _CapturingBus()
        bus2 = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus1)
        bridge.emit("on_session_start", session_id="s1")
        assert len(bus1.events) == 1
        assert len(bus2.events) == 0
        bridge.event_bus = bus2
        bridge.emit("on_session_start", session_id="s2")
        assert len(bus1.events) == 1  # unchanged
        assert len(bus2.events) == 1  # new bus received event


# ---------------------------------------------------------------------------
# Failure isolation tests
# ---------------------------------------------------------------------------


class TestFailureIsolation:
    """Bridge exceptions must never propagate to the caller."""

    def test_emit_survives_bus_emit_exception(self):
        class BrokenBus:
            subscriber_count = 1

            def emit(self, event):
                raise RuntimeError("bus broken")

        bridge = HermesEventBridge(event_bus=BrokenBus())
        bridge.emit("on_session_start", session_id="sess-abc")  # must not raise

    def test_emit_survives_none_metadata(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "on_session_start",
            session_id="sess-abc",
            task_id="",
            metadata=None,
        )
        assert len(bus.events) == 1

    def test_emit_survives_missing_session_id(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="")
        assert len(bus.events) == 1
        assert bus.events[0]["task_id"] == ""

    def test_emit_survives_bus_that_returns_none_subscriber_count(self):
        class WeirdBus:
            subscriber_count = None

            def emit(self, event):
                pass

        bridge = HermesEventBridge(event_bus=WeirdBus())
        bridge.emit("on_session_start", session_id="sess-abc")  # must not raise


# ---------------------------------------------------------------------------
# Identity / correlation tests
# ---------------------------------------------------------------------------


class TestIdentityCorrelation:
    """Session/task IDs must correlate across multiple events."""

    def test_same_session_id_across_multiple_events(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="sess-abc", task_id="task-1")
        bridge.emit("pre_tool_call", session_id="sess-abc", task_id="task-1")
        bridge.emit("post_tool_call", session_id="sess-abc", task_id="task-1")
        bridge.emit("on_session_end", session_id="sess-abc", task_id="task-1")
        assert len(bus.events) == 4
        for ev in bus.events:
            assert ev["task_id"] == "task-1"

    def test_different_sessions_produce_independent_events(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="sess-a", task_id="task-a")
        bridge.emit("on_session_start", session_id="sess-b", task_id="task-b")
        assert bus.events[0]["task_id"] == "task-a"
        assert bus.events[1]["task_id"] == "task-b"


# ---------------------------------------------------------------------------
# Completion / failure / cancellation tests
# ---------------------------------------------------------------------------


class TestTerminalEvents:
    """Terminal Hermes events must map to the correct Argus terminal event."""

    def test_execution_complete_produces_task_completed(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:complete", session_id="s1", metadata={"completed": True})
        assert bus.events[0]["event_type"] == EventType.TASK_COMPLETED

    def test_execution_failed_produces_task_failed(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:failed", session_id="s1", metadata={"failed": True})
        assert bus.events[0]["event_type"] == EventType.TASK_FAILED

    def test_execution_cancelled_produces_task_cancelled(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:cancelled", session_id="s1", metadata={"interrupted": True})
        assert bus.events[0]["event_type"] == EventType.TASK_CANCELLED

    def test_subagent_stop_produces_task_completed(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("subagent_stop", session_id="s1", metadata={"child_session_id": "child-1"})
        assert bus.events[0]["event_type"] == EventType.TASK_COMPLETED

    def test_api_request_error_produces_model_error(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "api_request_error",
            session_id="s1",
            metadata={"error": "rate limit exceeded"},
        )
        assert bus.events[0]["event_type"] == EventType.MODEL_ERROR
        assert bus.events[0]["data"]["error"] == "rate limit exceeded"


# ---------------------------------------------------------------------------
# Tool lifecycle tests
# ---------------------------------------------------------------------------


class TestToolLifecycle:
    """Tool start/complete events must map correctly."""

    def test_tool_started_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "tool.started",
            session_id="s1",
            task_id="t1",
            metadata={"tool_name": "read_file", "args": {"path": "main.py"}},
        )
        assert bus.events[0]["event_type"] == EventType.TOOL_CALL_STARTED
        assert bus.events[0]["data"]["tool_name"] == "read_file"

    def test_tool_completed_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "tool.completed",
            session_id="s1",
            task_id="t1",
            metadata={"tool_name": "write_file", "result": "ok"},
        )
        assert bus.events[0]["event_type"] == EventType.TOOL_CALL_COMPLETED
        assert bus.events[0]["data"]["result"] == "ok"

    def test_pre_tool_call_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "pre_tool_call",
            session_id="s1",
            task_id="t1",
            metadata={"tool_name": "git_diff"},
        )
        assert bus.events[0]["event_type"] == EventType.TOOL_CALL_STARTED

    def test_post_tool_call_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "post_tool_call",
            session_id="s1",
            task_id="t1",
            metadata={"tool_name": "git_diff"},
        )
        assert bus.events[0]["event_type"] == EventType.TOOL_CALL_COMPLETED


# ---------------------------------------------------------------------------
# Hermes event_callback compatibility test
# ---------------------------------------------------------------------------


class TestHermesCallbackCompatibility:
    """Bridge.emit matches the Hermes event_callback signature."""

    def test_emit_matches_event_callback_signature(self):
        """Hermes event_callback(event_name: str, data: dict) -> None."""
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)

        def hermes_event_callback(name: str, data: dict) -> None:
            # Hermes passes session_id in data; bridge.emit extracts it.
            session_id = str(data.get("session_id", ""))
            task_id = str(data.get("task_id", ""))
            bridge.emit(name, session_id=session_id, task_id=task_id, metadata=data)

        hermes_event_callback("on_session_start", {"session_id": "s1", "task_id": "t1"})
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_REGISTERED
        assert bus.events[0]["task_id"] == "t1"


# ---------------------------------------------------------------------------
# Hermes-specific event name tests
# ---------------------------------------------------------------------------


class TestHermesSpecificEvents:
    """Bridge handles Hermes-specific event names correctly."""

    def test_tool_started_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "tool.started",
            session_id="s1",
            task_id="t1",
            metadata={
                "tool_id": "tc-1",
                "name": "terminal",
                "args": {"command": "pwd"},
            },
        )
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TOOL_CALL_STARTED
        assert bus.events[0]["task_id"] == "t1"
        assert bus.events[0]["data"]["name"] == "terminal"

    def test_tool_completed_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "tool.completed",
            session_id="s1",
            task_id="t1",
            metadata={
                "tool_id": "tc-1",
                "name": "terminal",
                "args": {"command": "pwd"},
                "result": "done",
            },
        )
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TOOL_CALL_COMPLETED
        assert bus.events[0]["data"]["result"] == "done"

    def test_session_compress_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "session:compress",
            session_id="s1",
            task_id="t1",
            metadata={
                "in_place": False,
                "compression_count": 1,
            },
        )
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_STATE_CHANGED
        assert bus.events[0]["data"]["in_place"] is False

    def test_execution_start_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:start", session_id="s1", task_id="t1", metadata={})
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_STARTED

    def test_execution_complete_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:complete", session_id="s1", task_id="t1", metadata={})
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_COMPLETED

    def test_execution_failed_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:failed", session_id="s1", task_id="t1", metadata={})
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_FAILED

    def test_execution_cancelled_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("execution:cancelled", session_id="s1", task_id="t1", metadata={})
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.TASK_CANCELLED

    def test_runtime_error_event(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit(
            "error",
            session_id="s1",
            task_id="t1",
            metadata={
                "message": "model timeout",
            },
        )
        assert len(bus.events) == 1
        assert bus.events[0]["event_type"] == EventType.RUNTIME_ERROR
        assert bus.events[0]["data"]["message"] == "model timeout"


# ---------------------------------------------------------------------------
# Identity correlation across multiple events
# ---------------------------------------------------------------------------


class TestIdentityCorrelationExtended:
    """Same session_id maps to same task_id across multiple events."""

    def test_session_id_correlated_across_events(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="s1", task_id="t1", metadata={})
        bridge.emit("pre_llm_call", session_id="s1", task_id="t1", metadata={})
        bridge.emit("tool.started", session_id="s1", task_id="t1", metadata={})
        bridge.emit("on_session_end", session_id="s1", task_id="t1", metadata={"completed": True})

        assert len(bus.events) == 4
        assert all(e["metadata"]["session_id"] == "s1" for e in bus.events)
        assert all(e["task_id"] == "t1" for e in bus.events)

    def test_session_id_falls_back_to_task_id(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="s1", metadata={})

        assert len(bus.events) == 1
        assert bus.events[0]["task_id"] == "s1"

    def test_explicit_task_id_takes_precedence(self):
        bus = _CapturingBus()
        bridge = HermesEventBridge(event_bus=bus)
        bridge.emit("on_session_start", session_id="s1", task_id="explicit-task", metadata={})

        assert bus.events[0]["task_id"] == "explicit-task"


# ---------------------------------------------------------------------------
# EventBus failure isolation
# ---------------------------------------------------------------------------


class TestEventBusFailureIsolation:
    """Bridge isolates EventBus failures."""

    def test_eventbus_emit_exception_does_not_propagate(self):
        class _BadBus:
            def emit(self, event):
                raise RuntimeError("bus dead")

        bridge = HermesEventBridge(event_bus=_BadBus())
        bridge.emit("on_session_start", session_id="s1", task_id="t1", metadata={})
        bridge.emit("pre_llm_call", session_id="s1", task_id="t1", metadata={})

    def test_eventbus_none_is_noop(self):
        bridge = HermesEventBridge(event_bus=None)
        bridge.emit("on_session_start", session_id="s1", task_id="t1", metadata={})
        bridge.emit("tool.started", session_id="s1", task_id="t1", metadata={})
        bridge.emit("on_session_end", session_id="s1", task_id="t1", metadata={"completed": True})
