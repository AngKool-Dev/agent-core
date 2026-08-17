"""
Tests for AgentCore persistence & recovery architecture (Phase 7).

Tests cover:
- PersistenceBackend: abstract interface
- InMemoryPersistenceBackend: full CRUD, schema versioning, events
- FilesystemPersistenceBackend: atomic writes, schema versioning, path resolution
- EventStore: abstract interface
- InMemoryEventStore: append, query, clear, filters
- FilesystemEventStore: append, query, clear, filters
- TaskPersistenceManager: checkpointing, recovery, security filtering, failure isolation
- Security: sensitive data filtering, output bounds
- Agent integration: persistence checkpointing, backward compatibility
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agentcore.persistence import (
    PersistenceBackend,
    InMemoryPersistenceBackend,
    FilesystemPersistenceBackend,
    EventStore,
    InMemoryEventStore,
    FilesystemEventStore,
    TaskPersistenceManager,
    create_persistence_manager,
    _sanitize_for_persistence,
    _contains_sensitive_data,
    CURRENT_SCHEMA_VERSION,
)
from agentcore.task import Task, TaskState, PlanStep, StepStatus
from agentcore.events import EventBus, EventType, AgentEvent, create_event
from agentcore.agent import Agent, AgentConfig, create_agent
from agentcore.config import user_data_dir
from tests.test_mock_runtime import MockRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id: str = "task-abc123", state: TaskState = TaskState.RUNNING) -> Task:
    task = Task(task_id=task_id, user_request="Test task", project="test-project")
    task.current_state = state
    task.plan = [PlanStep(action="act", description="Do something").to_dict()]
    task.tool_results = [{"tool": "read_file", "success": True, "output": "hello world"}]
    return task


# ---------------------------------------------------------------------------
# PersistenceBackend interface tests
# ---------------------------------------------------------------------------

class TestPersistenceBackendInterface:
    def test_backend_is_abstract(self):
        with pytest.raises(TypeError):
            PersistenceBackend()

    def test_backend_requires_save_task(self):
        class Incomplete(PersistenceBackend):
            def load_task(self, task_id):
                return None
            def delete_task(self, task_id):
                return False
            def list_tasks(self):
                return []
            def save_event(self, event_dict):
                return False
            def get_events(self, task_id, limit=100):
                return []
            def clear(self, task_id=None):
                return 0
        with pytest.raises(TypeError):
            Incomplete()

    def test_backend_all_methods_required(self):
        class Partial(PersistenceBackend):
            def save_task(self, task_id, task_dict, schema_version=1):
                return True
        with pytest.raises(TypeError):
            Partial()


# ---------------------------------------------------------------------------
# InMemoryPersistenceBackend tests
# ---------------------------------------------------------------------------

class TestInMemoryPersistenceBackend:
    def test_save_and_load_task(self):
        backend = InMemoryPersistenceBackend()
        task_dict = {"task_id": "t1", "user_request": "test"}
        assert backend.save_task("t1", task_dict) is True
        loaded = backend.load_task("t1")
        assert loaded["task_id"] == "t1"
        assert loaded["user_request"] == "test"
        assert loaded["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_schema_version_stored(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {}, schema_version=2)
        loaded = backend.load_task("t1")
        assert loaded["schema_version"] == 2

    def test_default_schema_version(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {})
        loaded = backend.load_task("t1")
        assert loaded["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_load_missing_task_returns_none(self):
        backend = InMemoryPersistenceBackend()
        assert backend.load_task("nonexistent") is None

    def test_delete_task(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {})
        assert backend.delete_task("t1") is True
        assert backend.load_task("t1") is None
        assert backend.delete_task("t1") is False

    def test_list_tasks(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {})
        backend.save_task("t2", {})
        assert set(backend.list_tasks()) == {"t1", "t2"}

    def test_save_and_get_events(self):
        backend = InMemoryPersistenceBackend()
        backend.save_event({"task_id": "t1", "type": "test"})
        events = backend.get_events("t1")
        assert len(events) == 1
        assert events[0]["type"] == "test"

    def test_get_events_empty_for_missing_task(self):
        backend = InMemoryPersistenceBackend()
        assert backend.get_events("nonexistent") == []

    def test_get_events_limit(self):
        backend = InMemoryPersistenceBackend()
        for i in range(10):
            backend.save_event({"task_id": "t1", "index": i})
        events = backend.get_events("t1", limit=3)
        assert len(events) == 3
        assert events[0]["index"] == 7

    def test_clear_specific_task(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {})
        backend.save_task("t2", {})
        backend.save_event({"task_id": "t1", "type": "e1"})
        backend.save_event({"task_id": "t2", "type": "e2"})
        count = backend.clear("t1")
        assert count >= 2
        assert backend.load_task("t1") is None
        assert backend.load_task("t2") is not None

    def test_clear_all(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {})
        backend.save_event({"task_id": "t1", "type": "e1"})
        count = backend.clear()
        assert count >= 2
        assert backend.list_tasks() == []
        assert backend.get_events("t1") == []

    def test_full_crud_cycle(self):
        backend = InMemoryPersistenceBackend()
        backend.save_task("t1", {"name": "original"})
        assert backend.load_task("t1")["name"] == "original"
        backend.save_task("t1", {"name": "updated"})
        assert backend.load_task("t1")["name"] == "updated"
        assert backend.delete_task("t1") is True
        assert backend.load_task("t1") is None

    def test_close_is_noop(self):
        backend = InMemoryPersistenceBackend()
        backend.close()  # should not raise


# ---------------------------------------------------------------------------
# FilesystemPersistenceBackend tests
# ---------------------------------------------------------------------------

class TestFilesystemPersistenceBackend:
    def test_save_and_load_task(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        task_dict = {"task_id": "t1", "user_request": "test"}
        assert backend.save_task("t1", task_dict) is True
        loaded = backend.load_task("t1")
        assert loaded["task_id"] == "t1"
        assert loaded["user_request"] == "test"
        assert loaded["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_default_path_uses_user_data_dir(self):
        backend = FilesystemPersistenceBackend()
        assert backend._base_path == user_data_dir() / "tasks"

    def test_custom_base_path(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "custom")
        assert backend._base_path == tmp_path / "custom"

    def test_atomic_write_no_partial_files(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {"data": "value"})
        task_file = tmp_path / "tasks" / "t1.json"
        assert task_file.exists()
        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("**/*.tmp"))
        assert len(tmp_files) == 0

    def test_load_missing_task_returns_none(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        assert backend.load_task("nonexistent") is None

    def test_delete_task(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {})
        assert backend.delete_task("t1") is True
        assert backend.load_task("t1") is None

    def test_list_tasks(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {})
        backend.save_task("t2", {})
        assert set(backend.list_tasks()) == {"t1", "t2"}

    def test_save_and_get_events(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_event({"task_id": "t1", "type": "test"})
        events = backend.get_events("t1")
        assert len(events) == 1
        assert events[0]["type"] == "test"

    def test_events_appended_to_jsonl(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_event({"task_id": "t1", "index": 1})
        backend.save_event({"task_id": "t1", "index": 2})
        event_file = tmp_path / "events" / "t1.jsonl"
        assert event_file.exists()
        lines = event_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_get_events_limit(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        for i in range(10):
            backend.save_event({"task_id": "t1", "index": i})
        events = backend.get_events("t1", limit=3)
        assert len(events) == 3
        assert events[-1]["index"] == 9

    def test_clear_specific_task(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {})
        backend.save_task("t2", {})
        backend.save_event({"task_id": "t1", "type": "e1"})
        backend.save_event({"task_id": "t2", "type": "e2"})
        count = backend.clear("t1")
        assert count >= 2
        assert backend.load_task("t1") is None
        assert backend.load_task("t2") is not None

    def test_clear_all(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {})
        backend.save_event({"task_id": "t1", "type": "e1"})
        count = backend.clear()
        assert count >= 2
        assert backend.list_tasks() == []

    def test_corrupt_json_handled_gracefully(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        task_dir = tmp_path / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "bad.json").write_text("not json")
        assert backend.load_task("bad") is None

    def test_corrupt_event_line_skipped(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        event_path = tmp_path / "events" / "t1.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text('{"valid": true}\nnot json\n{"valid": false}\n')
        events = backend.get_events("t1")
        assert len(events) == 2

    def test_close_is_noop(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.close()  # should not raise


# ---------------------------------------------------------------------------
# EventStore interface tests
# ---------------------------------------------------------------------------

class TestEventStoreInterface:
    def test_store_is_abstract(self):
        with pytest.raises(TypeError):
            EventStore()

    def test_store_requires_append(self):
        class Incomplete(EventStore):
            def get_events(self, task_id, limit=100, since=None):
                return []
            def clear(self, task_id=None):
                return 0
        with pytest.raises(TypeError):
            Incomplete()


# ---------------------------------------------------------------------------
# InMemoryEventStore tests
# ---------------------------------------------------------------------------

class TestInMemoryEventStore:
    def test_append_and_get(self):
        store = InMemoryEventStore()
        store.append({"task_id": "t1", "type": "start"})
        events = store.get_events("t1")
        assert len(events) == 1
        assert events[0]["type"] == "start"

    def test_get_events_empty_for_missing(self):
        store = InMemoryEventStore()
        assert store.get_events("nonexistent") == []

    def test_get_events_limit(self):
        store = InMemoryEventStore()
        for i in range(10):
            store.append({"task_id": "t1", "index": i})
        events = store.get_events("t1", limit=3)
        assert len(events) == 3
        assert events[-1]["index"] == 9

    def test_get_events_since_filter(self):
        store = InMemoryEventStore()
        store.append({"task_id": "t1", "timestamp": "2024-01-01T00:00:00+00:00", "index": 1})
        store.append({"task_id": "t1", "timestamp": "2024-01-02T00:00:00+00:00", "index": 2})
        events = store.get_events("t1", since="2024-01-01T00:00:01+00:00")
        assert len(events) == 1
        assert events[0]["index"] == 2

    def test_clear_specific(self):
        store = InMemoryEventStore()
        store.append({"task_id": "t1", "type": "e1"})
        store.append({"task_id": "t2", "type": "e2"})
        count = store.clear("t1")
        assert count == 1
        assert store.get_events("t1") == []
        assert len(store.get_events("t2")) == 1

    def test_clear_all(self):
        store = InMemoryEventStore()
        store.append({"task_id": "t1", "type": "e1"})
        store.append({"task_id": "t2", "type": "e2"})
        count = store.clear()
        assert count == 2
        assert store.get_events("t1") == []
        assert store.get_events("t2") == []


# ---------------------------------------------------------------------------
# FilesystemEventStore tests
# ---------------------------------------------------------------------------

class TestFilesystemEventStore:
    def test_append_and_get(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path)
        store.append({"task_id": "t1", "type": "start"})
        events = store.get_events("t1")
        assert len(events) == 1
        assert events[0]["type"] == "start"

    def test_default_path_uses_user_data_dir(self):
        store = FilesystemEventStore()
        assert store._base_path == user_data_dir() / "events"

    def test_custom_base_path(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path / "events")
        assert store._base_path == tmp_path / "events"

    def test_get_events_limit(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path)
        for i in range(10):
            store.append({"task_id": "t1", "index": i})
        events = store.get_events("t1", limit=3)
        assert len(events) == 3
        assert events[-1]["index"] == 9

    def test_get_events_since_filter(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path)
        store.append({"task_id": "t1", "timestamp": "2024-01-01T00:00:00+00:00", "index": 1})
        store.append({"task_id": "t1", "timestamp": "2024-01-02T00:00:00+00:00", "index": 2})
        events = store.get_events("t1", since="2024-01-01T00:00:01+00:00")
        assert len(events) == 1
        assert events[0]["index"] == 2

    def test_clear_specific(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path)
        store.append({"task_id": "t1", "type": "e1"})
        store.append({"task_id": "t2", "type": "e2"})
        count = store.clear("t1")
        assert count == 1
        assert store.get_events("t1") == []
        assert len(store.get_events("t2")) == 1

    def test_clear_all(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path)
        store.append({"task_id": "t1", "type": "e1"})
        store.append({"task_id": "t2", "type": "e2"})
        count = store.clear()
        assert count == 2
        assert store.get_events("t1") == []

    def test_append_creates_directory(self, tmp_path):
        store = FilesystemEventStore(base_path=tmp_path / "new" / "dir")
        store.append({"task_id": "t1", "type": "e1"})
        assert (tmp_path / "new" / "dir" / "t1.jsonl").exists()


# ---------------------------------------------------------------------------
# TaskPersistenceManager tests
# ---------------------------------------------------------------------------

class TestTaskPersistenceManager:
    def test_checkpoint_saves_task(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        bus = EventBus()
        mgr = TaskPersistenceManager(backend=backend, event_store=store, event_bus=bus)
        task = _make_task()
        mgr.checkpoint(task)
        loaded = backend.load_task(task.task_id)
        assert loaded is not None
        assert loaded["user_request"] == "Test task"

    def test_checkpoint_skips_terminal_tasks(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        task = _make_task(state=TaskState.COMPLETED)
        mgr.checkpoint(task)
        assert backend.load_task(task.task_id) is None

    def test_checkpoint_emits_event(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        bus = EventBus()
        mgr = TaskPersistenceManager(backend=backend, event_store=store, event_bus=bus)
        task = _make_task()
        events = []
        bus.subscribe(lambda e: events.append(e))
        mgr.checkpoint(task)
        assert any(e.event_type == EventType.TASK_STATE_CHANGED for e in events)

    def test_checkpoint_failure_isolation(self):
        class FailingBackend(PersistenceBackend):
            def save_task(self, task_id, task_dict, schema_version=1):
                raise RuntimeError("fail")
            def load_task(self, task_id):
                return None
            def delete_task(self, task_id):
                return False
            def list_tasks(self):
                return []
            def save_event(self, event_dict):
                return False
            def get_events(self, task_id, limit=100):
                return []
            def clear(self, task_id=None):
                return 0
        backend = FailingBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        task = _make_task()
        mgr.checkpoint(task)  # should not raise

    def test_load_task_returns_task_object(self):
        backend = InMemoryPersistenceBackend()
        mgr = TaskPersistenceManager(backend=backend)
        task = _make_task()
        backend.save_task(task.task_id, task.to_dict())
        loaded = mgr.load_task(task.task_id)
        assert isinstance(loaded, Task)
        assert loaded.task_id == task.task_id
        assert loaded.user_request == "Test task"

    def test_recover_incomplete_tasks(self):
        backend = InMemoryPersistenceBackend()
        mgr = TaskPersistenceManager(backend=backend)
        incomplete = _make_task(task_id="incomplete", state=TaskState.RUNNING)
        complete = _make_task(task_id="complete", state=TaskState.COMPLETED)
        backend.save_task(incomplete.task_id, incomplete.to_dict())
        backend.save_task(complete.task_id, complete.to_dict())
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert recovered[0].task_id == "incomplete"

    def test_recover_emits_events(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        bus = EventBus()
        mgr = TaskPersistenceManager(backend=backend, event_store=store, event_bus=bus)
        task = _make_task(state=TaskState.RUNNING)
        backend.save_task(task.task_id, task.to_dict())
        events = []
        bus.subscribe(lambda e: events.append(e))
        recovered = mgr.recover_incomplete_tasks()
        assert len(recovered) == 1
        assert any(e.event_type == EventType.TASK_STATE_CHANGED for e in events)

    def test_delete_task_removes_both_task_and_events(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        backend.save_task("t1", {})
        store.append({"task_id": "t1", "type": "e1"})
        assert mgr.delete_task("t1") is True
        assert backend.load_task("t1") is None
        assert store.get_events("t1") == []

    def test_get_task_events(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        store.append({"task_id": "t1", "type": "e1"})
        store.append({"task_id": "t1", "type": "e2"})
        events = mgr.get_task_events("t1")
        assert len(events) == 2

    def test_save_event_delegates_to_event_store(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        event = create_event(EventType.TASK_STARTED, task_id="t1")
        mgr.save_event(event)
        assert len(store.get_events("t1")) == 1

    def test_create_persistence_manager_defaults(self):
        mgr = create_persistence_manager()
        assert isinstance(mgr.backend, InMemoryPersistenceBackend)
        assert isinstance(mgr.event_store, InMemoryEventStore)

    def test_create_persistence_manager_filesystem(self, tmp_path):
        mgr = create_persistence_manager(use_filesystem=True, base_path=tmp_path)
        assert isinstance(mgr.backend, FilesystemPersistenceBackend)
        assert isinstance(mgr.event_store, FilesystemEventStore)

    def test_set_event_bus(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        bus = EventBus()
        mgr.set_event_bus(bus)
        assert mgr._event_bus is bus

    def test_close_calls_backend_close(self):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)
        mgr.close()  # should not raise


# ---------------------------------------------------------------------------
# Security filtering tests
# ---------------------------------------------------------------------------

class TestSecurityFiltering:
    def test_password_redacted(self):
        result = _sanitize_for_persistence({"note": "My password is secret123"})
        assert result["note"] == "[REDACTED]"

    def test_api_key_redacted(self):
        result = _sanitize_for_persistence({"config": "API_KEY=sk-12345"})
        assert result["config"] == "[REDACTED]"

    def test_token_redacted(self):
        result = _sanitize_for_persistence({"auth": "access_token=xyz"})
        assert result["auth"] == "[REDACTED]"

    def test_normal_content_not_redacted(self):
        result = _sanitize_for_persistence({"text": "The build uses cargo"})
        assert result["text"] == "The build uses cargo"

    def test_nested_dict_filtered(self):
        result = _sanitize_for_persistence({
            "outer": {"inner": {"password": "secret"}}
        })
        assert result["outer"]["inner"]["password"] == "[REDACTED]"

    def test_list_filtered(self):
        result = _sanitize_for_persistence({"items": ["normal", "secret password here", "ok"]})
        assert result["items"][0] == "normal"
        assert result["items"][1] == "[REDACTED]"
        assert result["items"][2] == "ok"

    def test_output_bounded(self):
        long_text = "x" * 5000
        result = _sanitize_for_persistence({"text": long_text})
        assert len(result["text"]) == 2000

    def test_list_bounded(self):
        long_list = [{"text": f"item {i}"} for i in range(200)]
        result = _sanitize_for_persistence({"items": long_list})
        assert len(result["items"]) == 100

    def test_non_dict_returned_as_is(self):
        assert _sanitize_for_persistence("plain string") == "plain string"
        assert _sanitize_for_persistence(42) == 42
        assert _sanitize_for_persistence(None) is None

    def test_sensitive_patterns_case_insensitive(self):
        result = _sanitize_for_persistence({"text": "PASSWORD=secret"})
        assert result["text"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------

class TestAgentPersistenceIntegration:
    def test_agent_with_persistence_checkpoints(self, tmp_path):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        bus = EventBus()
        mgr = TaskPersistenceManager(backend=backend, event_store=store, event_bus=bus)

        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            persistence=mgr,
        )
        agent.execute("Test task", str(tmp_path))
        assert backend.load_task(agent.current_task.task_id) is not None

    def test_agent_without_persistence_backward_compat(self, tmp_path):
        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Test task", str(tmp_path))
        assert "success" in result

    def test_create_agent_with_persistence(self, tmp_path):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = create_persistence_manager(backend=backend, event_store=store)
        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
            persistence=mgr,
        )
        agent.config.enable_verification = False
        result = agent.execute("Test", str(tmp_path))
        assert "success" in result


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------

class TestPersistenceBackwardCompatibility:
    def test_existing_agent_works_without_persistence(self, tmp_path):
        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Test task", str(tmp_path))
        assert "success" in result
        assert "task" in result

    def test_create_agent_without_persistence(self, tmp_path):
        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )
        agent.config.enable_verification = False
        result = agent.execute("Test", str(tmp_path))
        assert "success" in result

    def test_task_to_dict_still_works(self):
        task = _make_task()
        data = task.to_dict()
        assert data["task_id"] == "task-abc123"
        assert data["current_state"] == "RUNNING"

    def test_task_from_dict_still_works(self):
        data = {
            "task_id": "task-abc123",
            "user_request": "Test",
            "project": "proj",
            "selected_skills": [],
            "attributes": {},
            "project_context": {},
            "memory_context": {},
            "current_state": "RUNNING",
            "plan": [],
            "actions": [],
            "tool_results": [],
            "changes": [],
            "test_results": {},
            "verification": {},
            "errors": [],
            "hypotheses": [],
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
        task = Task.from_dict(data)
        assert task.task_id == "task-abc123"
        assert task.current_state == TaskState.RUNNING

    def test_memory_manager_still_works(self):
        from agentcore.memory import InMemoryBackend, MemoryManager
        backend = InMemoryBackend()
        mgr = MemoryManager(backend)
        result = mgr.store("fact", "test content")
        assert result is not None
        assert result["content"] == "test content"


# ---------------------------------------------------------------------------
# Phase 7 Hardening: Crash-safety tests
# ---------------------------------------------------------------------------

class TestCrashSafety:
    def test_atomic_write_preserves_existing_on_failure(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {"version": 1})
        loaded_before = backend.load_task("t1")
        assert loaded_before["version"] == 1

        original_dumps = json.dump
        call_count = 0

        def failing_dumps(*args, **kwargs):
            call_count += 1
            raise TypeError("Simulated serialization failure")

        with patch("json.dump", side_effect=failing_dumps):
            result = backend.save_task("t1", {"version": 2})
        assert result is False

        loaded_after = backend.load_task("t1")
        assert loaded_after["version"] == 1

    def test_recovery_after_failed_checkpoint(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {"state": "running", "step": 1})

        original_dumps = json.dump

        def failing_dumps(*args, **kwargs):
            raise TypeError("Simulated failure")

        with patch("json.dump", side_effect=failing_dumps):
            result = backend.save_task("t1", {"state": "running", "step": 2})
        assert result is False

        loaded = backend.load_task("t1")
        assert loaded["state"] == "running"
        assert loaded["step"] == 1

    def test_corrupt_checkpoint_file_returns_none(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        task_file = tmp_path / "tasks" / "t1.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text("{bad json")
        assert backend.load_task("t1") is None

    def test_incomplete_json_checkpoint_returns_none(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        task_file = tmp_path / "tasks" / "t1.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text('{"task_id": "t1", "user_request": ')
        assert backend.load_task("t1") is None

    def test_missing_parent_directory_handled(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path / "deep" / "nested" / "path")
        assert backend.save_task("t1", {"data": "value"}) is True
        assert backend.load_task("t1")["data"] == "value"

    def test_no_tmp_files_left_after_success(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {"data": "value"})
        tmp_files = list(tmp_path.glob("**/*.tmp"))
        assert len(tmp_files) == 0

    def test_no_tmp_files_left_after_failure(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {"data": "value"})

        original_dumps = json.dump

        def failing_dumps(*args, **kwargs):
            raise TypeError("Simulated failure")

        with patch("json.dump", side_effect=failing_dumps):
            backend.save_task("t1", {"data": "new_value"})
        tmp_files = list(tmp_path.glob("**/*.tmp"))
        assert len(tmp_files) == 0


# ---------------------------------------------------------------------------
# Phase 7 Hardening: Recovery tests
# ---------------------------------------------------------------------------

class TestRecovery:
    def test_checkpoint_recover_roundtrip(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        store = FilesystemEventStore(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend, event_store=store)

        task = _make_task(task_id="roundtrip-task")
        task.hypotheses.append({"statement": "test hypothesis", "supporting_evidence": ["e1"], "contradicting_evidence": [], "status": "PROPOSED"})
        mgr.checkpoint(task)

        recovered = mgr.load_task("roundtrip-task")
        assert recovered is not None
        assert recovered.task_id == "roundtrip-task"
        assert recovered.user_request == "Test task"
        assert recovered.current_state == TaskState.RUNNING
        assert len(recovered.hypotheses) == 1
        assert recovered.hypotheses[0]["statement"] == "test hypothesis"

    def test_recover_preserves_plan_steps(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="plan-task")
        task.plan = [
            PlanStep(action="step1", description="First", status=StepStatus.COMPLETED).to_dict(),
            PlanStep(action="step2", description="Second", status=StepStatus.PENDING).to_dict(),
        ]
        mgr.checkpoint(task)
        recovered = mgr.load_task("plan-task")
        assert recovered is not None
        assert len(recovered.plan) == 2
        assert recovered.plan[0]["action"] == "step1"
        assert recovered.plan[0]["status"] == "COMPLETED"
        assert recovered.plan[1]["status"] == "PENDING"

    def test_recover_preserves_memory_context(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="memory-task")
        task.memory_context = {"results": [{"id": "m1", "content": "fact"}], "count": 1}
        mgr.checkpoint(task)
        recovered = mgr.load_task("memory-task")
        assert recovered is not None
        assert recovered.memory_context["count"] == 1
        assert recovered.memory_context["results"][0]["content"] == "fact"

    def test_recover_preserves_task_metadata(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="meta-task")
        task.selected_skills = ["debugging", "testing"]
        task.attributes = {"confidence": 0.9, "model": "test-model"}
        task.errors = ["error1"]
        mgr.checkpoint(task)
        recovered = mgr.load_task("meta-task")
        assert recovered is not None
        assert recovered.selected_skills == ["debugging", "testing"]
        assert recovered.attributes["confidence"] == 0.9
        assert recovered.errors == ["error1"]

    def test_recover_terminal_task_loadable_directly(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        completed = _make_task(task_id="completed-task", state=TaskState.COMPLETED)
        backend.save_task(completed.task_id, completed.to_dict())
        recovered = mgr.load_task("completed-task")
        assert recovered is not None
        assert recovered.current_state == TaskState.COMPLETED
        assert recovered.is_terminal() is True

    def test_recover_running_task(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="running-task", state=TaskState.RUNNING)
        mgr.checkpoint(task)
        recovered = mgr.load_task("running-task")
        assert recovered is not None
        assert recovered.current_state == TaskState.RUNNING
        assert recovered.is_terminal() is False

    def test_recover_cancelled_task(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="cancelled-task", state=TaskState.CANCELLED)
        backend.save_task(task.task_id, task.to_dict())
        recovered = mgr.load_task("cancelled-task")
        assert recovered is not None
        assert recovered.current_state == TaskState.CANCELLED

    def test_recover_failed_task(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="failed-task", state=TaskState.FAILED)
        backend.save_task(task.task_id, task.to_dict())
        recovered = mgr.load_task("failed-task")
        assert recovered is not None
        assert recovered.current_state == TaskState.FAILED

    def test_multiple_checkpoints_recover_latest(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="multi-task")
        mgr.checkpoint(task)
        task.plan = [PlanStep(action="updated", description="Updated step").to_dict()]
        mgr.checkpoint(task)

        recovered = mgr.load_task("multi-task")
        assert recovered is not None
        assert recovered.plan[0]["action"] == "updated"

    def test_corrupted_latest_checkpoint_safe(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="corrupt-task")
        mgr.checkpoint(task)

        task_file = tmp_path / "tasks" / "corrupt-task.json"
        task_file.write_text("{corrupt json")

        recovered = mgr.load_task("corrupt-task")
        assert recovered is None

    def test_recover_incomplete_tasks_excludes_terminal(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        completed = _make_task(task_id="completed", state=TaskState.COMPLETED)
        failed = _make_task(task_id="failed", state=TaskState.FAILED)
        cancelled = _make_task(task_id="cancelled", state=TaskState.CANCELLED)
        running = _make_task(task_id="running", state=TaskState.RUNNING)

        for t in [completed, failed, cancelled, running]:
            mgr.checkpoint(t)

        recovered = mgr.recover_incomplete_tasks()
        recovered_ids = {t.task_id for t in recovered}
        assert recovered_ids == {"running"}

    def test_task_id_stable_across_checkpoints(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task(task_id="stable-id")
        mgr.checkpoint(task)
        mgr.checkpoint(task)

        assert task.task_id in backend.list_tasks()

    def test_timestamps_remain_serializable(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)

        task = _make_task()
        mgr.checkpoint(task)
        recovered = mgr.load_task(task.task_id)
        assert recovered is not None
        assert "T" in recovered.created_at
        assert "T" in recovered.updated_at


# ---------------------------------------------------------------------------
# Phase 7 Hardening: Schema versioning tests
# ---------------------------------------------------------------------------

class TestSchemaVersioning:
    def test_current_schema_version_persisted(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        backend.save_task("t1", {"task_id": "t1"})
        loaded = backend.load_task("t1")
        assert loaded["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_recovery_accepts_current_schema(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)
        task = _make_task(task_id="t1")
        backend.save_task("t1", task.to_dict())
        recovered = mgr.load_task("t1")
        assert recovered is not None
        assert recovered.task_id == "t1"

    def test_unsupported_future_schema_fails_safely(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)
        task_file = tmp_path / "tasks" / "t1.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps({"task_id": "t1", "schema_version": CURRENT_SCHEMA_VERSION + 99}))
        recovered = mgr.load_task("t1")
        assert recovered is None

    def test_missing_schema_version_handled_safely(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)
        task = _make_task(task_id="t1")
        backend.save_task("t1", task.to_dict())
        task_file = tmp_path / "tasks" / "t1.json"
        raw = json.loads(task_file.read_text())
        raw.pop("schema_version", None)
        task_file.write_text(json.dumps(raw))
        recovered = mgr.load_task("t1")
        assert recovered is None

    def test_schema_version_mismatch_handled_safely(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)
        task_file = tmp_path / "tasks" / "t1.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps({"task_id": "t1", "schema_version": 0}))
        recovered = mgr.load_task("t1")
        assert recovered is None

    def test_schema_version_does_not_mutate_original(self, tmp_path):
        backend = FilesystemPersistenceBackend(base_path=tmp_path)
        mgr = TaskPersistenceManager(backend=backend)
        task = _make_task()
        mgr.checkpoint(task)
        loaded = backend.load_task(task.task_id)
        assert loaded["schema_version"] == CURRENT_SCHEMA_VERSION
        recovered = mgr.load_task(task.task_id)
        assert recovered is not None
        assert not hasattr(recovered, "schema_version")


# ---------------------------------------------------------------------------
# Phase 7 Hardening: Agent integration boundary tests
# ---------------------------------------------------------------------------

class TestAgentPersistenceBoundaries:
    def test_checkpoint_at_analyzing_boundary(self, tmp_path):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        bus = EventBus()
        mgr = TaskPersistenceManager(backend=backend, event_store=store, event_bus=bus)

        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            persistence=mgr,
        )
        agent.execute("Test task", str(tmp_path))
        assert backend.load_task(agent.current_task.task_id) is not None

    def test_persistence_none_is_transparent(self, tmp_path):
        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
        )
        result = agent.execute("Test task", str(tmp_path))
        assert result["success"] is True
        assert "task" in result

    def test_persistence_failure_does_not_crash_agent(self, tmp_path):
        class FailingBackend(PersistenceBackend):
            def save_task(self, task_id, task_dict, schema_version=1):
                raise RuntimeError("persistence failure")
            def load_task(self, task_id):
                return None
            def delete_task(self, task_id):
                return False
            def list_tasks(self):
                return []
            def save_event(self, event_dict):
                return False
            def get_events(self, task_id, limit=100):
                return []
            def clear(self, task_id=None):
                return 0

        backend = FailingBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)

        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            persistence=mgr,
        )
        result = agent.execute("Test task", str(tmp_path))
        assert "success" in result

    def test_checkpoint_skips_terminal_tasks(self, tmp_path):
        backend = InMemoryPersistenceBackend()
        store = InMemoryEventStore()
        mgr = TaskPersistenceManager(backend=backend, event_store=store)

        runtime = MockRuntime(responses=["Done"])
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

        memory = MemoryManager(InMemoryBackend())
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            persistence=mgr,
        )
        agent.execute("Test task", str(tmp_path))
        task_id = agent.current_task.task_id
        loaded = backend.load_task(task_id)
        assert loaded is not None
        assert loaded["current_state"] == "PLANNING"


# ---------------------------------------------------------------------------
# Phase 7 Hardening: Security edge-case tests
# ---------------------------------------------------------------------------

class TestSecurityEdgeCases:
    def test_password_in_nested_list(self):
        result = _sanitize_for_persistence({
            "logs": [
                "normal log",
                "user entered password=secret123",
                "another normal log",
            ]
        })
        assert result["logs"][0] == "normal log"
        assert result["logs"][1] == "[REDACTED]"
        assert result["logs"][2] == "another normal log"

    def test_tool_result_with_error_redacted(self):
        tool_result = {
            "tool": "run_command",
            "success": False,
            "error": "Permission denied for /etc/shadow",
            "output": "normal output",
        }
        result = _sanitize_for_persistence(tool_result)
        assert result["error"] == "Permission denied for /etc/shadow"
        assert result["output"] == "normal output"

    def test_event_payload_with_sensitive_data(self):
        event = {
            "task_id": "t1",
            "event_type": "tool_call.completed",
            "data": {
                "tool": "shell",
                "arguments": {"command": "echo secret_token=xyz"},
            },
        }
        result = _sanitize_for_persistence(event)
        assert result["data"]["arguments"]["command"] == "[REDACTED]"

    def test_task_metadata_with_credentials(self):
        task_meta = {
            "attributes": {
                "api_key": "sk-12345",
                "model": "claude-3",
            }
        }
        result = _sanitize_for_persistence(task_meta)
        assert result["attributes"]["api_key"] == "sk-12345"
        assert result["attributes"]["model"] == "claude-3"

    def test_deeply_nested_sensitive_data(self):
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "secret": "my-secret-value",
                        "normal": "keep this",
                    }
                }
            }
        }
        result = _sanitize_for_persistence(data)
        assert result["level1"]["level2"]["level3"]["secret"] == "[REDACTED]"
        assert result["level1"]["level2"]["level3"]["normal"] == "keep this"

    def test_empty_string_not_redacted(self):
        result = _sanitize_for_persistence({"text": ""})
        assert result["text"] == ""

    def test_integer_values_preserved(self):
        result = _sanitize_for_persistence({"count": 42, "flag": True, "nothing": None})
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["nothing"] is None

    def test_path_values_converted_to_string(self):
        from pathlib import Path
        result = _sanitize_for_persistence({"path": Path("/tmp/test.txt")})
        assert isinstance(result["path"], str)
        assert result["path"] == str(Path("/tmp/test.txt"))

    def test_boolean_password_substring_not_overmatched(self):
        result = _sanitize_for_persistence({
            "password_length": 8,
            "password_reset": True,
            "secret_number": 42,
        })
        assert result["password_length"] == 8
        assert result["password_reset"] is True
        assert result["secret_number"] == 42

    def test_credential_pattern_variants(self):
        variants = ["credential", "credentials", "CREDENTIAL", "Credential"]
        for variant in variants:
            result = _sanitize_for_persistence({"text": f"Use {variant} to login"})
            assert result["text"] == "[REDACTED]", f"Failed for variant: {variant}"

    def test_api_key_case_variants(self):
        variants = ["api_key", "API_KEY", "Api_Key", "apikey", "APIKEY"]
        for variant in variants:
            result = _sanitize_for_persistence({"text": f"{variant}=value"})
            assert result["text"] == "[REDACTED]", f"Failed for variant: {variant}"
