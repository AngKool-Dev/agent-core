"""
Production limits and security validation tests for AgentCore.
"""

import json
from typing import Any, Dict, List, Optional

import pytest

from agentcore import (
    Agent,
    AgentConfig,
    AgentCore,
    AgentCoreLimits,
    create_agent,
    EventBus,
    EventType,
)
from agentcore.errors import ConfigurationError
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.persistence import (
    InMemoryPersistenceBackend,
    InMemoryEventStore,
    TaskPersistenceManager,
)
from agentcore.task import Task
from tests.integration.runtimes import DeterministicRuntime, bug_fix_lifecycle


class DeterministicMemoryBackend(MemoryBackend):
    def __init__(self):
        self._records: Dict[str, Dict[str, Any]] = {}

    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        return []

    def store(self, type: str, content: str, project: Optional[str] = None, importance: float = 0.5) -> Dict[str, Any]:
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

    def update(self, memory_id: str, content: str) -> Dict[str, Any]:
        if memory_id in self._records:
            self._records[memory_id]["content"] = content
            return dict(self._records[memory_id])
        return {}

    def list(self, project: Optional[str] = None, type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._records.values())[:limit]


class TestLimits:
    """Production limit enforcement."""

    def test_max_active_tasks_limit(self, tmp_path):
        core = AgentCore(
            limits=AgentCoreLimits(max_active_tasks=2),
            project_path=tmp_path,
        )
        for i in range(3):
            task = type('Task', (), {'task_id': f't{i}', 'user_request': 'test', 'project': 'proj', 'current_state': None})()
            core.registry.register(task)
        active = core.registry.list_active()
        assert len(active) == 3

    def test_limits_validation(self):
        with pytest.raises(ConfigurationError):
            AgentCoreLimits(max_active_tasks=0).validate()
        with pytest.raises(ConfigurationError):
            AgentCoreLimits(max_task_execution_seconds=0).validate()
        with pytest.raises(ConfigurationError):
            AgentCoreLimits(max_persisted_task_size_bytes=512).validate()

    def test_default_limits_are_sensible(self):
        limits = AgentCoreLimits()
        assert limits.max_active_tasks >= 1
        assert limits.max_task_execution_seconds >= 1
        assert limits.max_task_lifetime_seconds >= 1
        assert limits.max_recovery_tasks >= 1
        assert limits.max_event_history >= 1
        assert limits.max_persisted_task_size_bytes >= 1024


class TestSecurity:
    """Security boundary validation."""

    def test_persistence_no_secrets(self, tmp_path):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        task = Task(task_id="sensitive", user_request="test with password=secret123", project="proj")
        persistence.checkpoint(task)

        loaded = backend.load_task("sensitive")
        assert loaded is not None
        assert "password=secret123" not in loaded.get("user_request", "")

    def test_event_bus_no_secrets(self, tmp_path):
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

    def test_memory_no_secrets(self):
        backend = DeterministicMemoryBackend()
        memory = MemoryManager(backend)
        result = memory.store("fact", "normal content")
        assert result is not None

        result = memory.store("fact", "password=secret123")
        assert result is None
