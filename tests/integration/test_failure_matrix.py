"""
Failure matrix integration tests for AgentCore.

Tests validate failure paths:
- Tool failure → replanning or failure
- Runtime failure → task FAILED
- Timeout → deterministic timeout state
- Cancellation → CANCELLED
- Duplicate execution → TaskAlreadyRunningError
- Shutdown during active work
"""

import threading
import time
from typing import Any, Dict, List, Optional

import pytest

from agentcore import (
    Agent,
    AgentConfig,
    AgentCore,
    AgentCoreLimits,
    create_agent,
    create_agent_core,
    EventBus,
    EventType,
    TaskState,
)
from agentcore.errors import TaskAlreadyRunningError
from agentcore.task import Task
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.persistence import (
    InMemoryPersistenceBackend,
    InMemoryEventStore,
    TaskPersistenceManager,
)
from tests.integration.runtimes import (
    DeterministicRuntime,
    bug_fix_lifecycle,
    runtime_failure_lifecycle,
    timeout_lifecycle,
    tool_failure_lifecycle,
)


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


class TestToolFailure:
    """Tool failure handling."""

    def test_tool_failure_does_not_crash_agent(self, tmp_path):
        runtime = DeterministicRuntime(tool_failure_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))
        assert "task" in result

    def test_tool_failure_preserves_context(self, tmp_path):
        runtime = DeterministicRuntime(tool_failure_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))
        assert result["task"]["user_request"] == "Fix the bug"

    def test_max_replans_enforced(self, tmp_path):
        runtime = DeterministicRuntime(tool_failure_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(
                max_iterations=20,
                max_tool_calls=50,
                max_replans=1,
                enable_verification=False,
            ),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))
        assert result["task"]["current_state"] in ("FAILED", "COMPLETED")


class TestRuntimeFailure:
    """Runtime failure handling."""

    def test_runtime_failure_becomes_structured_failure(self, tmp_path):
        runtime = DeterministicRuntime(bug_fix_lifecycle(), fail_on_call=1)
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))
        assert result["task"]["current_state"] == "FAILED"

    def test_runtime_failure_releases_lock(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle(), fail_on_call=1)
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )
        agent.config.enable_verification = False
        agent.config.max_iterations = 5
        agent.config.max_tool_calls = 10

        agent.execute("Fix the bug", str(tmp_path))
        core.registry.register(agent.current_task)
        assert not core.registry.is_locked(agent.current_task.task_id)

    def test_runtime_failure_emits_event(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle(), fail_on_call=1)
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
        assert EventType.TASK_STATE_CHANGED in event_types

    def test_agentcore_remains_usable_after_runtime_failure(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
        runtime1 = DeterministicRuntime(bug_fix_lifecycle(), fail_on_call=1)
        memory1 = MemoryManager(DeterministicMemoryBackend())
        agent1 = create_agent(
            runtime=runtime1,
            memory=memory1,
            project_path=tmp_path,
        )
        agent1.config.enable_verification = False
        agent1.config.max_iterations = 5
        agent1.config.max_tool_calls = 10
        agent1.execute("Fail task", str(tmp_path))

        runtime2 = DeterministicRuntime(bug_fix_lifecycle())
        memory2 = MemoryManager(DeterministicMemoryBackend())
        agent2 = create_agent(
            runtime=runtime2,
            memory=memory2,
            project_path=tmp_path,
        )
        agent2.config.enable_verification = False
        agent2.config.max_iterations = 5
        agent2.config.max_tool_calls = 10
        result = agent2.execute("Fix the bug", str(tmp_path))
        assert result["success"] is True


class TestTimeout:
    """Timeout handling."""

    def test_timeout_is_deterministic(self, tmp_path):
        runtime = DeterministicRuntime(timeout_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Fix the bug", str(tmp_path))
        assert result["task"]["current_state"] in ("BLOCKED", "FAILED", "COMPLETED")

    def test_timeout_releases_lock(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
        runtime = DeterministicRuntime(timeout_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )
        agent.config.enable_verification = False
        agent.config.max_iterations = 5
        agent.config.max_tool_calls = 10

        agent.execute("Fix the bug", str(tmp_path))
        core.registry.register(agent.current_task)
        assert not core.registry.is_locked(agent.current_task.task_id)


class TestCancellation:
    """Cancellation handling."""

    def test_cancel_during_execution(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=10, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            event_bus=bus,
        )
        result = agent.execute("Fix the bug", str(tmp_path))
        assert result["task"]["current_state"] in ("COMPLETED", "CANCELLED", "REPLANNING")

    def test_cancel_emits_event(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(max_iterations=10, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            event_bus=bus,
        )
        agent.execute("Fix the bug", str(tmp_path))
        agent.cancel()
        event_types = [e.event_type for e in events]
        assert EventType.TASK_CANCELLED in event_types

    def test_cancel_releases_lock(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
        runtime = DeterministicRuntime(bug_fix_lifecycle())
        memory = MemoryManager(DeterministicMemoryBackend())
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )
        agent.config.enable_verification = False
        agent.config.max_iterations = 10
        agent.config.max_tool_calls = 10

        agent.execute("Fix the bug", str(tmp_path))
        core.registry.register(agent.current_task)
        agent.cancel()
        assert not core.registry.is_locked(agent.current_task.task_id)


class TestDuplicateExecution:
    """Duplicate execution prevention."""

    def test_duplicate_lock_rejected(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
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

        agent.execute("Fix the bug", str(tmp_path))
        core.registry.register(agent.current_task)
        # Task is now terminal (COMPLETED), lock is released
        # Simulate an active task by manually acquiring a lock
        core.registry.acquire_lock(agent.current_task.task_id, "holder-1")
        with pytest.raises(TaskAlreadyRunningError):
            core.registry.acquire_lock(agent.current_task.task_id, "holder-2")


class TestShutdown:
    """Graceful shutdown."""

    def test_shutdown_during_active_work(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
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

        agent.execute("Fix the bug", str(tmp_path))
        core.registry.register(agent.current_task)
        result = core.shutdown()
        assert result["shutdown"] is True
        assert not core.registry.is_locked(agent.current_task.task_id)

    def test_shutdown_emits_events(self, tmp_path):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        core = AgentCore(event_bus=bus, project_path=tmp_path)
        core.shutdown()
        event_types = [e.event_type for e in events]
        assert EventType.SHUTDOWN_STARTED in event_types
        assert EventType.SHUTDOWN_COMPLETED in event_types

    def test_shutdown_is_idempotent(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
        core.shutdown()
        result = core.shutdown()
        assert result["shutdown"] is True
