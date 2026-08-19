"""
Observability integration tests for AgentCore.

Validates that the existing EventBus can reconstruct the lifecycle of a task.
"""

import json
from typing import Any

from agentcore import (
    Agent,
    AgentConfig,
    AgentCore,
    EventBus,
    EventType,
)
from agentcore.memory import MemoryBackend, MemoryManager
from tests.integration.runtimes import DeterministicRuntime, bug_fix_lifecycle


class DeterministicMemoryBackend(MemoryBackend):
    def __init__(self):
        self._records: dict[str, dict[str, Any]] = {}

    def search(
        self, query: str, project: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        return []

    def store(
        self, type: str, content: str, project: str | None = None, importance: float = 0.5
    ) -> dict[str, Any]:
        record = {
            "id": f"mem-{len(self._records)}",
            "type": type,
            "content": content,
            "project": project,
            "importance": importance,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        self._records[record["id"]] = record
        return record

    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        if memory_id in self._records:
            self._records[memory_id]["content"] = content
            return dict(self._records[memory_id])
        return {}

    def list(
        self, project: str | None = None, type: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        return list(self._records.values())[:limit]


class TestObservability:
    """EventBus lifecycle observability."""

    def test_event_lifecycle_sequence(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            event_bus=bus,
        )
        agent.execute("Fix the bug", str(tmp_path))

        event_types = [e.event_type for e in events]
        assert EventType.TASK_STARTED in event_types
        assert EventType.TASK_STATE_CHANGED in event_types
        assert EventType.TASK_COMPLETED in event_types

    def test_events_contain_task_id(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            event_bus=bus,
        )
        agent.execute("Fix the bug", str(tmp_path))

        for event in events:
            assert event.task_id is not None
            assert len(event.task_id) > 0

    def test_events_are_json_serializable(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            event_bus=bus,
        )
        agent.execute("Fix the bug", str(tmp_path))

        for event in events:
            data = event.to_dict()
            json.dumps(data)

    def test_no_secrets_in_events(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            event_bus=bus,
        )
        agent.execute("Fix the bug", str(tmp_path))

        for event in events:
            data_str = json.dumps(event.to_dict())
            assert "sk-12345" not in data_str
            assert "password123" not in data_str.lower()

    def test_shutdown_events_emitted(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        core = AgentCore(event_bus=bus, project_path=tmp_path)
        core.shutdown()
        event_types = [e.event_type for e in events]
        assert EventType.SHUTDOWN_STARTED in event_types
        assert EventType.SHUTDOWN_COMPLETED in event_types

    def test_registry_events_emitted(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        core = AgentCore(event_bus=bus, project_path=tmp_path)
        task = type(
            "Task",
            (),
            {"task_id": "t1", "user_request": "test", "project": "proj", "current_state": None},
        )()
        core.registry.register(task)
        event_types = [e.event_type for e in events]
        assert EventType.TASK_REGISTERED in event_types
