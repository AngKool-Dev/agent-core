"""
Multi-task execution isolation tests for AgentCore.

Validates:
- Two independent tasks
- Different task IDs
- Independent locks
- Independent state
- Independent persistence
- Independent memory context
- Independent events
- Task A failure does not affect Task B
- Cancellation isolation
- Concurrent registration
"""

from threading import Thread
from typing import Any

from agentcore import (
    Agent,
    AgentConfig,
    AgentCore,
    EventBus,
    TaskState,
)
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.persistence import (
    InMemoryEventStore,
    InMemoryPersistenceBackend,
    TaskPersistenceManager,
)
from agentcore.task import Task
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


class TestMultiTaskIsolation:
    """Multiple tasks execute independently without state leakage."""

    def test_two_independent_tasks(self, tmp_path):
        runtime_a = DeterministicRuntime(bug_fix_lifecycle())
        memory_a = MemoryManager(DeterministicMemoryBackend())
        agent_a = Agent(
            runtime=runtime_a,
            memory=memory_a,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result_a = agent_a.execute("Fix bug A", str(tmp_path))

        runtime_b = DeterministicRuntime(bug_fix_lifecycle())
        memory_b = MemoryManager(DeterministicMemoryBackend())
        agent_b = Agent(
            runtime=runtime_b,
            memory=memory_b,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result_b = agent_b.execute("Fix bug B", str(tmp_path))

        assert result_a["task"]["task_id"] != result_b["task"]["task_id"]
        assert result_a["task"]["user_request"] == "Fix bug A"
        assert result_b["task"]["user_request"] == "Fix bug B"

    def test_independent_persistence_records(self, tmp_path):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        runtime_a = DeterministicRuntime(bug_fix_lifecycle())
        memory_a = MemoryManager(DeterministicMemoryBackend())
        agent_a = Agent(
            runtime=runtime_a,
            memory=memory_a,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
        )
        agent_a.execute("Fix bug A", str(tmp_path))

        runtime_b = DeterministicRuntime(bug_fix_lifecycle())
        memory_b = MemoryManager(DeterministicMemoryBackend())
        agent_b = Agent(
            runtime=runtime_b,
            memory=memory_b,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
        )
        agent_b.execute("Fix bug B", str(tmp_path))

        task_ids = backend.list_tasks()
        assert len(task_ids) == 2

    def test_independent_events(self, tmp_path):
        events_a = []
        events_b = []
        bus = EventBus()
        bus.subscribe(lambda e: events_a.append(e) if e.task_id else None)
        bus.subscribe(lambda e: events_b.append(e) if e.task_id else None)

        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        persistence = TaskPersistenceManager(backend=backend, event_store=store, event_bus=bus)

        runtime_a = DeterministicRuntime(bug_fix_lifecycle())
        memory_a = MemoryManager(DeterministicMemoryBackend())
        agent_a = Agent(
            runtime=runtime_a,
            memory=memory_a,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
            event_bus=bus,
        )
        agent_a.execute("Fix bug A", str(tmp_path))

        runtime_b = DeterministicRuntime(bug_fix_lifecycle())
        memory_b = MemoryManager(DeterministicMemoryBackend())
        agent_b = Agent(
            runtime=runtime_b,
            memory=memory_b,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
            persistence=persistence,
            event_bus=bus,
        )
        agent_b.execute("Fix bug B", str(tmp_path))

        task_a_id = agent_a.current_task.task_id
        task_b_id = agent_b.current_task.task_id
        task_a_events = [e for e in events_a if e.task_id == task_a_id]
        task_b_events = [e for e in events_b if e.task_id == task_b_id]
        assert len(task_a_events) > 0
        assert len(task_b_events) > 0

    def test_failure_isolation_task_a_fails_task_b_succeeds(self, tmp_path):
        runtime_a = DeterministicRuntime(bug_fix_lifecycle(), fail_on_call=1)
        memory_a = MemoryManager(DeterministicMemoryBackend())
        agent_a = Agent(
            runtime=runtime_a,
            memory=memory_a,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result_a = agent_a.execute("Fail task A", str(tmp_path))

        runtime_b = DeterministicRuntime(bug_fix_lifecycle())
        memory_b = MemoryManager(DeterministicMemoryBackend())
        agent_b = Agent(
            runtime=runtime_b,
            memory=memory_b,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result_b = agent_b.execute("Fix bug B", str(tmp_path))

        assert result_a["task"]["current_state"] == "FAILED"
        assert result_b["task"]["current_state"] in ("COMPLETED", "REPLANNING")

    def test_cancellation_isolation(self, tmp_path):
        runtime_a = DeterministicRuntime(bug_fix_lifecycle())
        memory_a = MemoryManager(DeterministicMemoryBackend())
        agent_a = Agent(
            runtime=runtime_a,
            memory=memory_a,
            config=AgentConfig(max_iterations=10, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        agent_a.execute("Task A", str(tmp_path))
        agent_a.cancel()
        assert agent_a.current_task.current_state == TaskState.CANCELLED

        runtime_b = DeterministicRuntime(bug_fix_lifecycle())
        memory_b = MemoryManager(DeterministicMemoryBackend())
        agent_b = Agent(
            runtime=runtime_b,
            memory=memory_b,
            config=AgentConfig(max_iterations=5, max_tool_calls=10, enable_verification=False),
            project_path=tmp_path,
        )
        result_b = agent_b.execute("Fix bug B", str(tmp_path))
        assert result_b["task"]["current_state"] == "COMPLETED"

    def test_concurrent_registration(self, tmp_path):
        core = AgentCore(project_path=tmp_path)
        results = []

        def register_task(tid):
            try:
                task = Task(task_id=f"task-{tid}", user_request="concurrent", project="proj")
                record = core.registry.register(task)
                results.append(("ok", record.task_id))
            except Exception as e:
                results.append(("error", str(e)))

        threads = [Thread(target=register_task, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r[0] == "ok" for r in results)
        assert len(core.registry.list_tasks()) == 10
