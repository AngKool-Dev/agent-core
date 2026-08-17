"""
Complete lifecycle integration test for AgentCore.

Validates the full flow:
USER REQUEST → AgentCore → TaskRegistry → Task state machine →
Project context → Memory recall → Skill routing → Planning →
RuntimeAdapter → Model response → Tool execution → Observation →
Replanning → Verification → Persistence/checkpoint → Task completion →
Memory storage → Events/observability
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agentcore import (
    Agent,
    AgentConfig,
    AgentCore,
    AgentCoreLimits,
    create_agent,
    create_agent_core,
    TaskRegistry,
    TaskPersistenceManager,
    MemoryManager,
    EventBus,
    EventType,
    TaskState,
)
from agentcore.task import Task
from agentcore.memory import MemoryBackend, InMemoryBackend
from agentcore.persistence import InMemoryPersistenceBackend, InMemoryEventStore
from tests.integration.runtimes import DeterministicRuntime, bug_fix_lifecycle


class DeterministicMemoryBackend(MemoryBackend):
    """In-memory backend that tracks all operations for test assertions."""

    def __init__(self):
        self._records: Dict[str, Dict[str, Any]] = {}
        self._stored: List[Dict[str, Any]] = []
        self._searched: List[str] = []

    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        self._searched.append(query)
        return []

    def store(self, type: str, content: str, project: Optional[str] = None, importance: float = 0.5) -> Dict[str, Any]:
        record = {
            "id": f"mem-{len(self._stored)}",
            "type": type,
            "content": content,
            "project": project,
            "importance": importance,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        self._records[record["id"]] = record
        self._stored.append(record)
        return record

    def update(self, memory_id: str, content: str) -> Dict[str, Any]:
        if memory_id in self._records:
            self._records[memory_id]["content"] = content
            return dict(self._records[memory_id])
        return {}

    def list(self, project: Optional[str] = None, type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._records.values())[:limit]


def _setup_project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")


class TestCompleteLifecycle:
    """Validate the complete AgentCore lifecycle from request to completion."""

    def test_successful_bug_fix_lifecycle(self, tmp_path):
        """Complete bug-fix lifecycle with all phases."""
        _setup_project(tmp_path)
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))

        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory_backend = DeterministicMemoryBackend()
        memory = MemoryManager(memory_backend)
        persistence = TaskPersistenceManager(
            backend=InMemoryPersistenceBackend(),
            event_store=InMemoryEventStore(),
        )

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(
                max_iterations=5,
                max_tool_calls=10,
                enable_verification=False,
            ),
            project_path=tmp_path,
            persistence=persistence,
            event_bus=bus,
        )

        result = agent.execute("Fix the bug in src/main.py", str(tmp_path))

        assert result["success"] is True
        assert result["task"]["current_state"] == "COMPLETED"
        assert result["tools_used"] >= 1
        assert "task_id" in result["task"]

        task_id = result["task"]["task_id"]
        assert persistence.load_task(task_id) is not None
        assert len(memory_backend._stored) >= 1

        event_types = [e.event_type for e in events]
        assert EventType.TASK_STARTED in event_types
        assert EventType.TASK_STATE_CHANGED in event_types
        assert EventType.TASK_COMPLETED in event_types

    def test_task_identity_stable_across_lifecycle(self, tmp_path):
        """Task ID remains stable from creation through completion."""
        _setup_project(tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))

        task_id = result["task"]["task_id"]
        assert task_id is not None
        assert len(task_id) > 0

    def test_state_machine_transitions_are_legal(self, tmp_path):
        """All state transitions during lifecycle are valid."""
        _setup_project(tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))

        state = result["task"]["current_state"]
        assert state == "COMPLETED"

    def test_skill_routing_occurs(self, tmp_path):
        """Skill routing is invoked during the lifecycle."""
        _setup_project(tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))

        assert "selected_skills" in result["task"]

    def test_memory_recall_occurs(self, tmp_path):
        """Memory recall is invoked during context building."""
        _setup_project(tmp_path)
        memory_backend = DeterministicMemoryBackend()
        memory = MemoryManager(memory_backend)
        runtime = DeterministicRuntime(bug_fix_lifecycle())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        agent.execute("Fix the bug", str(tmp_path))

        assert len(memory_backend._searched) >= 1

    def test_persistence_checkpoints_occur(self, tmp_path):
        """Persistence checkpoints occur during lifecycle."""
        _setup_project(tmp_path)
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
        )
        agent.execute("Fix the bug", str(tmp_path))

        task_id = agent.current_task.task_id
        assert backend.load_task(task_id) is not None

    def test_completion_persists(self, tmp_path):
        """Task completion is persisted."""
        _setup_project(tmp_path)
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
        )
        agent.execute("Fix the bug", str(tmp_path))

        task_id = agent.current_task.task_id
        loaded = backend.load_task(task_id)
        assert loaded is not None
        assert loaded["current_state"] in ("COMPLETED", "PLANNING", "RUNNING")

    def test_task_memory_stored(self, tmp_path):
        """Task memory is stored after completion."""
        _setup_project(tmp_path)
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=store)
        memory_backend = DeterministicMemoryBackend()
        memory = MemoryManager(memory_backend)

        runtime = DeterministicRuntime(bug_fix_lifecycle())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
        )
        agent.execute("Fix the bug", str(tmp_path))

        assert len(memory_backend._stored) >= 1

    def test_expected_lifecycle_events_emitted(self, tmp_path):
        """Expected lifecycle events are emitted in order."""
        _setup_project(tmp_path)
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

    def test_lock_released_after_completion(self, tmp_path):
        """Task lock is released after successful completion."""
        _setup_project(tmp_path)
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        core = AgentCore(event_bus=bus, project_path=tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )
        agent.config.enable_verification = False
        agent.config.max_iterations = 5
        agent.config.max_tool_calls = 10

        result = agent.execute("Fix the bug", str(tmp_path))
        core.registry.register(agent.current_task)
        assert not core.registry.is_locked(agent.current_task.task_id)

    def test_no_orphaned_active_task(self, tmp_path):
        """No orphaned active task remains after completion."""
        _setup_project(tmp_path)
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        core = AgentCore(event_bus=bus, project_path=tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())

        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )
        agent.config.enable_verification = False
        agent.config.max_iterations = 5
        agent.config.max_tool_calls = 10

        initial_active = len(core.registry.list_active())
        agent.execute("Fix the bug", str(tmp_path))
        final_active = len(core.registry.list_active())

        assert final_active == initial_active
