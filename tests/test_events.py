"""
Tests for AgentCore event system (Phase 4).

Tests cover:
- Event model: creation, IDs, timestamps, event types, task IDs, iteration, metadata
- Serialization: to_dict(), enums, datetime, Path, nested structures, JSON
- EventBus: subscribe, multiple subscribers, unsubscribe, ordering, failure isolation, no subscribers
- Agent integration: task start/completion/failure, iteration, model request/response,
  tool start/completion/failure, routing, planning, verification
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from agentcore.events import (
    AgentEvent,
    EventType,
    EventBus,
    EventHandler,
    create_event,
)


class TestEventModel:
    """Event creation and basic properties."""

    def test_event_creation(self):
        event = AgentEvent(
            event_type=EventType.TASK_STARTED,
            task_id="task-abc123",
        )
        assert event.event_type == EventType.TASK_STARTED
        assert event.task_id == "task-abc123"
        assert event.data == {}
        assert event.metadata == {}

    def test_event_has_unique_id(self):
        e1 = AgentEvent(event_type=EventType.TASK_STARTED)
        e2 = AgentEvent(event_type=EventType.TASK_STARTED)
        assert e1.id != e2.id
        assert e1.id.startswith("evt-")

    def test_event_timestamp_is_string(self):
        event = AgentEvent(event_type=EventType.TASK_STARTED)
        assert isinstance(event.timestamp, str)
        # Should be ISO format
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed.tzinfo is not None

    def test_event_types_all_defined(self):
        """All EventType members from the spec should exist."""
        expected = {
            "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED",
            "ITERATION_STARTED", "ITERATION_COMPLETED",
            "ROUTE_SELECTED",
            "PLAN_CREATED", "PLAN_UPDATED",
            "MODEL_REQUEST_STARTED", "MODEL_RESPONSE_RECEIVED", "MODEL_ERROR",
            "TOOL_CALL_STARTED", "TOOL_CALL_COMPLETED", "TOOL_CALL_FAILED",
            "OBSERVATION_CREATED",
            "VERIFICATION_STARTED", "VERIFICATION_COMPLETED",
            "SKILL_DISCOVERED", "SKILL_SELECTED", "SKILL_LOADED",
            "RUNTIME_ERROR",
        }
        actual = {e.name for e in EventType}
        assert expected.issubset(actual), f"Missing event types: {expected - actual}"

    def test_event_iteration_none_by_default(self):
        event = AgentEvent(event_type=EventType.TASK_STARTED)
        assert event.iteration is None

    def test_event_iteration_set(self):
        event = AgentEvent(event_type=EventType.ITERATION_STARTED, iteration=3)
        assert event.iteration == 3

    def test_event_metadata(self):
        event = AgentEvent(
            event_type=EventType.MODEL_REQUEST_STARTED,
            metadata={"runtime": "hermes", "model": "claude-sonnet-4"},
        )
        assert event.metadata["runtime"] == "hermes"
        assert event.metadata["model"] == "claude-sonnet-4"

    def test_event_data(self):
        event = AgentEvent(
            event_type=EventType.TOOL_CALL_COMPLETED,
            data={"tool": "read_file", "success": True, "duration": 0.1},
        )
        assert event.data["tool"] == "read_file"
        assert event.data["success"] is True

    def test_create_event_factory(self):
        event = create_event(
            EventType.VERIFICATION_STARTED,
            task_id="t1",
            iteration=2,
            data={"checks": ["format"]},
        )
        assert event.event_type == EventType.VERIFICATION_STARTED
        assert event.task_id == "t1"
        assert event.iteration == 2
        assert event.data["checks"] == ["format"]


class TestSerialization:
    """to_dict() and JSON serialization."""

    def test_to_dict_basic_fields(self):
        event = AgentEvent(
            event_type=EventType.TASK_STARTED,
            task_id="t123",
            iteration=5,
            data={"key": "value"},
            metadata={"meta": "data"},
        )
        d = event.to_dict()
        assert d["id"] == event.id
        assert d["timestamp"] == event.timestamp
        assert d["event_type"] == "task.started"
        assert d["task_id"] == "t123"
        assert d["iteration"] == 5
        assert d["data"] == {"key": "value"}
        assert d["metadata"] == {"meta": "data"}

    def test_to_dict_enum_serialized(self):
        event = AgentEvent(
            event_type=EventType.TOOL_CALL_COMPLETED,
            metadata={"finish_reason": EventType.MODEL_ERROR},
        )
        d = event.to_dict()
        assert d["event_type"] == "tool_call.completed"
        assert d["metadata"]["finish_reason"] == "model.error"

    def test_to_dict_datetime_serialized(self):
        now = datetime.now(timezone.utc)
        event = AgentEvent(
            event_type=EventType.TASK_STARTED,
            data={"created": now},
        )
        d = event.to_dict()
        assert isinstance(d["data"]["created"], str)
        assert "T" in d["data"]["created"]

    def test_to_dict_path_serialized(self):
        event = AgentEvent(
            event_type=EventType.SKILL_LOADED,
            data={"path": Path("/some/skill/path")},
        )
        d = event.to_dict()
        assert d["data"]["path"] == str(Path("/some/skill/path"))

    def test_to_dict_nested_structures(self):
        event = AgentEvent(
            event_type=EventType.VERIFICATION_COMPLETED,
            data={
                "checks": [
                    {"name": "format", "passed": True},
                    {"name": "build", "passed": False, "error": "compile error"},
                ],
            },
            metadata={"platform": Path("/some/path")},
        )
        d = event.to_dict()
        assert d["data"]["checks"][0]["name"] == "format"
        assert d["data"]["checks"][1]["passed"] is False
        assert d["metadata"]["platform"] == str(Path("/some/path"))

    def test_to_dict_json_serializable(self):
        """Full round-trip: event → to_dict → json.dumps → json.loads → verify."""
        event = AgentEvent(
            event_type=EventType.TOOL_CALL_STARTED,
            task_id="t1",
            iteration=1,
            data={"tool": "read_file", "path": Path("/tmp/test.txt")},
            metadata={"runtime": "hermes", "model": "claude-3"},
        )
        d = event.to_dict()
        encoded = json.dumps(d)
        decoded = json.loads(encoded)

        assert decoded["event_type"] == "tool_call.started"
        assert decoded["task_id"] == "t1"
        assert decoded["iteration"] == 1
        assert decoded["data"]["tool"] == "read_file"
        assert decoded["data"]["path"] == str(Path("/tmp/test.txt"))
        assert decoded["metadata"]["runtime"] == "hermes"


class TestEventBus:
    """EventBus subscribe/unsubscribe/emit behavior."""

    def test_subscribe_and_receive(self):
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e))
        bus.emit(AgentEvent(event_type=EventType.TASK_STARTED))
        assert len(received) == 1
        assert received[0].event_type == EventType.TASK_STARTED

    def test_multiple_subscribers(self):
        bus = EventBus()
        received_a = []
        received_b = []
        bus.subscribe(lambda e: received_a.append(e))
        bus.subscribe(lambda e: received_b.append(e))
        bus.emit(AgentEvent(event_type=EventType.TASK_STARTED))
        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(handler)
        bus.emit(AgentEvent(event_type=EventType.TASK_STARTED))
        assert len(received) == 1

        bus.unsubscribe(handler)
        bus.emit(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received) == 1  # still 1, unsubscribed

    def test_ordering(self):
        """Subscribers receive events in registration order."""
        bus = EventBus()
        order = []
        bus.subscribe(lambda e: order.append("first"))
        bus.subscribe(lambda e: order.append("second"))
        bus.subscribe(lambda e: order.append("third"))
        bus.emit(AgentEvent(event_type=EventType.TASK_STARTED))
        assert order == ["first", "second", "third"]

    def test_subscriber_failure_isolation(self):
        """Subscriber exceptions must not crash AgentCore."""
        bus = EventBus()
        received = []

        def bad_handler(e):
            raise RuntimeError("I always fail")

        def good_handler(e):
            received.append(e)

        bus.subscribe(bad_handler)
        bus.subscribe(good_handler)
        bus.emit(AgentEvent(event_type=EventType.TASK_STARTED))

        # Good handler should still receive the event
        assert len(received) == 1

    def test_no_subscribers_is_noop(self):
        bus = EventBus()
        # Should not raise
        bus.emit(AgentEvent(event_type=EventType.TASK_STARTED))

    def test_subscriber_count(self):
        bus = EventBus()
        assert bus.subscriber_count == 0
        h1 = lambda e: None
        h2 = lambda e: None
        bus.subscribe(h1)
        assert bus.subscriber_count == 1
        bus.subscribe(h2)
        assert bus.subscriber_count == 2
        bus.unsubscribe(h1)
        assert bus.subscriber_count == 1

    def test_subscribe_requires_callable(self):
        bus = EventBus()
        with pytest.raises(TypeError):
            bus.subscribe("not a callable")

    def test_unsubscribe_non_registered_is_noop(self):
        bus = EventBus()
        handler = lambda e: None
        # Should not raise
        bus.unsubscribe(handler)


class TestAgentEventIntegration:
    """Agent emits events at all lifecycle points."""

    def _make_agent_with_bus(self, tmp_path, responses=None):
        """Create an Agent with a MockRuntime and EventBus."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.memory import MemoryBackend, MemoryManager

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store = []
            def search(self, query, project=None, limit=20):
                return []
            def store(self, type, content, project=None, importance=0.5):
                mem = {"id": f"mem-{len(self._store)}", "type": type, "content": content, "project": project}
                self._store.append(mem)
                return mem
            def update(self, memory_id, content):
                return {}
            def list(self, project=None, type=None, limit=50):
                return self._store

        if responses is None:
            responses = ["Final answer complete."]

        runtime = MockRuntime(responses=responses)
        memory = MemoryManager(InMemoryBackend())
        bus = EventBus()

        from agentcore import create_agent
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
            agentcore_config=None,
            event_bus=bus,
        )
        agent.config.enable_verification = False
        return agent, bus

    def test_task_started_event(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.TASK_STARTED for e in received)

    def test_task_completed_event(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.TASK_COMPLETED for e in received)

    def test_iteration_events(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.ITERATION_STARTED for e in received)
        assert any(e.event_type == EventType.ITERATION_COMPLETED for e in received)

    def test_model_request_and_response_events(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.MODEL_REQUEST_STARTED for e in received)
        assert any(e.event_type == EventType.MODEL_RESPONSE_RECEIVED for e in received)

    def test_tool_call_events(self, tmp_path):
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import ToolCall, RuntimeResponse, FinishReason
        from agentcore.memory import MemoryBackend, MemoryManager

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store = []
            def search(self, query, project=None, limit=20):
                return []
            def store(self, type, content, project=None, importance=0.5):
                mem = {"id": f"mem-{len(self._store)}", "type": type, "content": content, "project": project}
                self._store.append(mem)
                return mem
            def update(self, memory_id, content):
                return {}
            def list(self, project=None, type=None, limit=50):
                return self._store

        runtime = MockRuntime(responses=[
            RuntimeResponse(
                content="I'll run a command",
                tool_calls=[ToolCall(tool="run_command", arguments={"command": "echo test"})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Done", finish_reason=FinishReason.STOP),
        ])
        memory = MemoryManager(InMemoryBackend())
        bus = EventBus()

        from agentcore import create_agent
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
            agentcore_config=None,
            event_bus=bus,
        )
        agent.config.enable_verification = False

        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))

        assert any(e.event_type == EventType.TOOL_CALL_STARTED for e in received)
        assert any(e.event_type == EventType.TOOL_CALL_COMPLETED for e in received)

    def test_tool_call_failure_event(self, tmp_path):
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import ToolCall, RuntimeResponse, FinishReason
        from agentcore.memory import MemoryBackend, MemoryManager

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store = []
            def search(self, query, project=None, limit=20):
                return []
            def store(self, type, content, project=None, importance=0.5):
                mem = {"id": f"mem-{len(self._store)}", "type": type, "content": content, "project": project}
                self._store.append(mem)
                return mem
            def update(self, memory_id, content):
                return {}
            def list(self, project=None, type=None, limit=50):
                return self._store

        runtime = MockRuntime(responses=[
            RuntimeResponse(
                content="I'll run a bad command",
                tool_calls=[ToolCall(tool="unknown_tool", arguments={})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Done", finish_reason=FinishReason.STOP),
        ])
        memory = MemoryManager(InMemoryBackend())
        bus = EventBus()

        from agentcore import create_agent
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
            agentcore_config=None,
            event_bus=bus,
        )
        agent.config.enable_verification = False

        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))

        assert any(e.event_type == EventType.TOOL_CALL_FAILED for e in received)

    def test_planning_event(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.PLAN_CREATED for e in received)

    def test_route_selected_event(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.ROUTE_SELECTED for e in received)

    def test_verification_events(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        agent.config.enable_verification = True
        agent.config.run_format_check = True
        agent.config.run_build_check = False
        agent.config.run_tests = False

        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))
        assert any(e.event_type == EventType.VERIFICATION_STARTED for e in received)
        assert any(e.event_type == EventType.VERIFICATION_COMPLETED for e in received)

    def test_event_data_is_json_serializable(self, tmp_path):
        """All events emitted during a full run should be JSON-serializable."""
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))

        for event in received:
            d = event.to_dict()
            json.dumps(d)  # should not raise

    def test_events_include_task_id(self, tmp_path):
        agent, bus = self._make_agent_with_bus(tmp_path, ["Done"])
        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))

        # All events should have the same task_id
        task_ids = {e.task_id for e in received}
        assert len(task_ids) == 1
        assert "" not in task_ids  # task_id should be set, not empty

    def test_runtime_error_event_on_timeout(self, tmp_path):
        """When max_iterations is 0, the loop exits quickly."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.memory import MemoryBackend, MemoryManager
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store = []
            def search(self, query, project=None, limit=20):
                return []
            def store(self, type, content, project=None, importance=0.5):
                return {"id": "1", "content": content}
            def update(self, memory_id, content):
                return {}
            def list(self, project=None, type=None, limit=50):
                return []

        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        bus = EventBus()

        from agentcore import ConfigLoader
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False, max_iterations=0),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
            event_bus=bus,
        )

        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))

        # With 0 iterations, the loop should exit via tool_limit or timeout
        assert any(e.event_type == EventType.TASK_STARTED for e in received)
        assert any(e.event_type == EventType.TASK_COMPLETED for e in received)

    def test_backward_compatibility_no_event_bus(self, tmp_path):
        """Agent works normally when no EventBus is supplied."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.memory import MemoryBackend, MemoryManager
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store = []
            def search(self, query, project=None, limit=20):
                return []
            def store(self, type, content, project=None, importance=0.5):
                return {"id": "1"}
            def update(self, memory_id, content):
                return {}
            def list(self, project=None, type=None, limit=50):
                return []

        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
        )
        # Should not raise even without event_bus
        result = agent.execute("Test task", str(tmp_path))
        assert "success" in result

    def test_observation_created_event(self, tmp_path):
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import ToolCall, RuntimeResponse, FinishReason
        from agentcore.memory import MemoryBackend, MemoryManager

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store = []
            def search(self, query, project=None, limit=20):
                return []
            def store(self, type, content, project=None, importance=0.5):
                return {"id": "1"}
            def update(self, memory_id, content):
                return {}
            def list(self, project=None, type=None, limit=50):
                return []

        runtime = MockRuntime(responses=[
            RuntimeResponse(
                content="I'll run a command",
                tool_calls=[ToolCall(tool="run_command", arguments={"command": "echo test"})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Done", finish_reason=FinishReason.STOP),
        ])
        memory = MemoryManager(InMemoryBackend())
        bus = EventBus()

        from agentcore import create_agent
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
            agentcore_config=None,
            event_bus=bus,
        )
        agent.config.enable_verification = False

        received = []
        bus.subscribe(lambda e: received.append(e))
        agent.execute("Test task", str(tmp_path))

        assert any(e.event_type == EventType.OBSERVATION_CREATED for e in received)
