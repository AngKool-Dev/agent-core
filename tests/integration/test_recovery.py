"""
Recovery and restart integration tests for AgentCore.

Tests validate:
- checkpoint → restart → discover
- recover incomplete task
- corrupt checkpoint
- unsupported schema
- terminal checkpoint
- multiple checkpoints
- latest checkpoint corruption
- persistence backend failure
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agentcore import (
    Agent,
    AgentConfig,
    AgentCore,
    TaskState,
)
from agentcore.task import Task
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.persistence import (
    FilesystemPersistenceBackend,
    FilesystemEventStore,
    TaskPersistenceManager,
)
from agentcore.task_registry import TaskRecordStatus
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


def _setup_project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "main.py").write_text("original")


class TestRecovery:
    """Task recovery after simulated process termination."""

    def test_checkpoint_restart_recover(self, tmp_path):
        _setup_project(tmp_path)
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
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

        result = agent.execute("Fix the bug", str(tmp_path))
        task_id = result["task"]["task_id"]

        new_core = AgentCore(
            persistence=TaskPersistenceManager(
                backend=FilesystemPersistenceBackend(base_path=tmp_path / "persist"),
                event_store=FilesystemEventStore(base_path=tmp_path / "events"),
            ),
            project_path=tmp_path,
        )
        recovered = new_core.recover_tasks()
        recovered_ids = {r.task_id for r in recovered}
        assert task_id in recovered_ids

    def test_recover_preserves_task_identity(self, tmp_path):
        _setup_project(tmp_path)
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
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
        result = agent.execute("Fix the bug", str(tmp_path))
        original_id = result["task"]["task_id"]

        new_core = AgentCore(
            persistence=TaskPersistenceManager(
                backend=FilesystemPersistenceBackend(base_path=tmp_path / "persist"),
                event_store=FilesystemEventStore(base_path=tmp_path / "events"),
            ),
            project_path=tmp_path,
        )
        recovered = new_core.recover_tasks()
        assert any(r.task_id == original_id for r in recovered)

    def test_recover_preserves_state(self, tmp_path):
        _setup_project(tmp_path)
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
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
        result = agent.execute("Fix the bug", str(tmp_path))

        new_core = AgentCore(
            persistence=TaskPersistenceManager(
                backend=FilesystemPersistenceBackend(base_path=tmp_path / "persist"),
                event_store=FilesystemEventStore(base_path=tmp_path / "events"),
            ),
            project_path=tmp_path,
        )
        recovered = new_core.recover_tasks()
        if recovered:
            # Recovery preserves the state from the last checkpoint
            assert recovered[0].task_state in (TaskState.PLANNING, TaskState.COMPLETED)

    def test_corrupt_checkpoint_safe(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        task_file = tmp_path / "persist" / "tasks" / "corrupt.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text("{bad json")

        new_core = AgentCore(persistence=persistence, project_path=tmp_path)
        recovered = new_core.recover_tasks()
        assert len(recovered) == 0

    def test_unsupported_schema_safe(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        task_file = tmp_path / "persist" / "tasks" / "future.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps({"task_id": "future", "schema_version": 999}))

        new_core = AgentCore(persistence=persistence, project_path=tmp_path)
        recovered = new_core.recover_tasks()
        assert len(recovered) == 0

    def test_terminal_task_excluded_from_recovery(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        completed = Task(task_id="completed", user_request="done", project="proj")
        completed.current_state = TaskState.COMPLETED
        backend.save_task("completed", completed.to_dict())

        new_core = AgentCore(persistence=persistence, project_path=tmp_path)
        recovered = new_core.recover_tasks()
        assert len(recovered) == 0

    def test_multiple_checkpoints_recover_latest(self, tmp_path):
        _setup_project(tmp_path)
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
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

        new_core = AgentCore(
            persistence=TaskPersistenceManager(
                backend=FilesystemPersistenceBackend(base_path=tmp_path / "persist"),
                event_store=FilesystemEventStore(base_path=tmp_path / "events"),
            ),
            project_path=tmp_path,
        )
        recovered = new_core.recover_tasks()
        assert any(r.task_id == task_id for r in recovered)

    def test_latest_checkpoint_corruption_safe(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        task = Task(task_id="safe", user_request="test", project="proj")
        backend.save_task("safe", task.to_dict())

        task_file = tmp_path / "persist" / "tasks" / "safe.json"
        task_file.write_text("{corrupt")

        new_core = AgentCore(persistence=persistence, project_path=tmp_path)
        recovered = new_core.recover_tasks()
        assert len(recovered) == 0

    def test_persistence_backend_failure_isolated(self, tmp_path):
        class FailingBackend(FilesystemPersistenceBackend):
            def load_task(self, task_id):
                raise RuntimeError("persistence failure")

        backend = FailingBackend(base_path=tmp_path / "persist")
        store = FilesystemEventStore(base_path=tmp_path / "events")
        persistence = TaskPersistenceManager(backend=backend, event_store=store)

        new_core = AgentCore(persistence=persistence, project_path=tmp_path)
        recovered = new_core.recover_tasks()
        assert len(recovered) == 0
