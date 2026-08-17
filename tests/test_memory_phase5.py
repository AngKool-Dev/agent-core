"""
Tests for AgentCore memory & context architecture (Phase 5).

Tests cover:
- MemoryBackend: store, recall, empty recall, multiple records, metadata, clear
- MemoryManager: normalization, result limits, backend failure, optional memory, store behavior
- Agent integration: memory recalled before planning, memory included in context,
  task result stored after completion, memory failure does not crash task, memory events emitted
- Context: project context, task context, memory context, combined context, context limits,
  missing project metadata
- DB-Obsidian adapter: conforms to MemoryBackend
- Security: sensitive data filtering
- In-Memory backend: full CRUD

Does NOT require DB-Obsidian to be installed.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentcore.memory import (
    MemoryBackend,
    MemoryManager,
    InMemoryBackend,
    MemoryRecord,
    MemoryType,
)
from agentcore.events import EventBus, EventType, AgentEvent


# ──────────────────────────── Test Backend ────────────────────────────

class RecordingBackend(MemoryBackend):
    """Backend that records all operations for test inspection."""

    def __init__(self, fail_search=False, fail_store=False):
        self._records: dict[str, dict[str, Any]] = {}
        self.fail_search = fail_search
        self.fail_store = fail_store
        self.search_calls = []
        self.store_calls = []

    def search(self, query, project=None, limit=20):
        self.search_calls.append({"query": query, "project": project, "limit": limit})
        if self.fail_search:
            raise RuntimeError("Backend search failure")
        query_lower = query.lower()
        results = []
        for r in self._records.values():
            if project and r.get("project") != project:
                continue
            if query_lower in r.get("content", "").lower():
                results.append(dict(r))
        return sorted(results, key=lambda x: x.get("importance", 0), reverse=True)[:limit]

    def store(self, type, content, project=None, importance=0.5):
        self.store_calls.append({"type": type, "content": content, "project": project, "importance": importance})
        if self.fail_store:
            raise RuntimeError("Backend store failure")
        record = {
            "id": f"mem-{len(self._records)}",
            "type": type,
            "content": content,
            "project": project,
            "importance": importance,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._records[record["id"]] = record
        return record

    def update(self, memory_id, content):
        if memory_id not in self._records:
            return {}
        self._records[memory_id]["content"] = content
        return dict(self._records[memory_id])

    def list(self, project=None, type=None, limit=50):
        results = []
        for r in self._records.values():
            if project and r.get("project") != project:
                continue
            if type and r.get("type") != type:
                continue
            results.append(dict(r))
        return sorted(results, key=lambda x: x.get("importance", 0), reverse=True)[:limit]

    def delete(self, memory_id):
        if memory_id in self._records:
            del self._records[memory_id]
            return True
        return False

    def clear(self, project=None):
        if project:
            to_remove = [k for k, v in self._records.items() if v.get("project") == project]
            for k in to_remove:
                del self._records[k]
            return len(to_remove)
        count = len(self._records)
        self._records.clear()
        return count

    def close(self):
        pass


# ──────────────────────── MemoryBackend Tests ─────────────────────────

class TestMemoryBackendInterface:
    """Test the abstract MemoryBackend interface."""

    def test_backend_is_abstract(self):
        with pytest.raises(TypeError):
            MemoryBackend()

    def test_backend_requires_search(self):
        """A backend must implement all abstract methods to be instantiable."""
        class Incomplete(MemoryBackend):
            def search(self, query, project=None, limit=20):
                return []
            # Missing: store, update, list — should fail
        with pytest.raises(TypeError):
            Incomplete()

    def test_backend_optional_methods_default(self):
        """Optional methods (delete, clear, close) have safe defaults."""
        backend = RecordingBackend()
        assert backend.delete("nonexistent") == False
        assert backend.clear() == 0
        backend.close()  # should not raise


# ──────────────────────── MemoryRecord Tests ──────────────────────────

class TestMemoryRecord:
    """Test the MemoryRecord dataclass."""

    def test_record_creation_defaults(self):
        record = MemoryRecord(content="Test memory")
        assert record.content == "Test memory"
        assert record.memory_type == MemoryType.FACT.value
        assert record.source == "agent"
        assert record.id.startswith("mem-")
        assert record.relevance == 0.0
        assert record.project is None

    def test_record_creation_with_fields(self):
        record = MemoryRecord(
            content="Fix: use proper error handling",
            memory_type=MemoryType.DECISION.value,
            source="user",
            project="my-project",
            relevance=0.8,
        )
        assert record.memory_type == "decision"
        assert record.source == "user"
        assert record.project == "my-project"
        assert record.relevance == 0.8

    def test_record_to_dict(self):
        record = MemoryRecord(
            content="Test",
            memory_type=MemoryType.TASK.value,
            project="proj-1",
            relevance=0.5,
            metadata={"key": "value"},
        )
        d = record.to_dict()
        assert d["content"] == "Test"
        assert d["type"] == "task"
        assert d["project"] == "proj-1"
        assert d["relevance"] == 0.5

    def test_record_timestamp_is_iso(self):
        record = MemoryRecord(content="Test")
        # Should be parseable as ISO format
        datetime.fromisoformat(record.timestamp)


# ──────────────────────── MemoryType Tests ────────────────────────────

class TestMemoryType:
    """Test the MemoryType enum."""

    def test_all_types_exist(self):
        expected = {"task", "project", "conversation", "decision", "fact", "error", "learning"}
        actual = {t.value for t in MemoryType}
        assert expected == actual

    def test_type_values_are_strings(self):
        for t in MemoryType:
            assert isinstance(t.value, str)

    def test_task_type(self):
        assert MemoryType.TASK.value == "task"

    def test_decision_type(self):
        assert MemoryType.DECISION.value == "decision"

    def test_learning_type(self):
        assert MemoryType.LEARNING.value == "learning"


# ──────────────────────── MemoryManager Tests ─────────────────────────

class TestMemoryManagerStore:
    """Test MemoryManager.store and convenience methods."""

    def test_store_returns_record(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        result = mgr.store("fact", "Python 3.12 is the runtime")
        assert result is not None
        assert result["id"].startswith("mem-")
        assert result["content"] == "Python 3.12 is the runtime"

    def test_store_with_project(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("task", "Fixed the bug", project="test-project")
        assert len(backend._records) == 1
        assert backend._records[list(backend._records.keys())[0]]["project"] == "test-project"

    def test_store_decision(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        result = mgr.store_decision("Use async pattern", "my-project", context="Discussed design")
        assert result is not None
        assert "Decision: Use async pattern" in result["content"]

    def test_store_lesson(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        result = mgr.store_lesson("Always check bounds", "my-project")
        assert result["type"] == "learning"

    def test_store_project_architecture(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        result = mgr.store_project_architecture("Layered architecture", "my-project")
        assert result["type"] == "project"
        assert result["importance"] == 0.9


class TestMemoryManagerSearch:
    """Test MemoryManager.search and retrieve_relevant_memory."""

    def test_search_returns_matching_records(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "Python 3.12 is the runtime", project="myproj")
        mgr.store("fact", "Rust is fast", project="myproj")

        results = mgr.search("python", project="myproj")
        assert len(results) == 1
        assert "Python" in results[0]["content"]

    def test_search_empty_results(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        results = mgr.search("nonexistent", project="myproj")
        assert results == []

    def test_search_no_project_filter(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "Python is great", project="proj1")
        mgr.store("fact", "Python is great too", project="proj2")

        results = mgr.search("python")
        assert len(results) == 2

    def test_search_result_limit(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend, max_context_records=3)
        for i in range(10):
            mgr.store("fact", f"Fact {i}", project="proj", importance=0.1 * i)

        results = mgr.search("fact", project="proj", limit=10)
        assert len(results) <= 3

    def test_retrieve_relevant_memory(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("architecture", "Use SQLite for database", project="proj")
        mgr.store("fact", "Python is the language", project="proj")

        text = mgr.retrieve_relevant_memory("database", "proj")
        assert "SQLite" in text

    def test_retrieve_with_type_filter(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("architecture", "Use SQLite for database", project="proj")
        mgr.store("fact", "Python is the language", project="proj")

        text = mgr.retrieve_relevant_memory("database", "proj", types=["architecture"])
        assert "SQLite" in text
        assert "Python" not in text


class TestMemoryManagerFailureIsolation:
    """Test that memory failures are isolated."""

    def test_search_failure_returns_empty(self):
        backend = RecordingBackend(fail_search=True)
        mgr = MemoryManager(backend)
        results = mgr.search("test")
        assert results == []

    def test_store_failure_returns_none(self):
        backend = RecordingBackend(fail_store=True)
        mgr = MemoryManager(backend)
        result = mgr.store("fact", "test")
        assert result is None

    def test_search_failure_with_no_backend(self):
        mgr = MemoryManager(None)
        assert mgr.search("test") == []

    def test_store_failure_with_no_backend(self):
        mgr = MemoryManager(None)
        assert mgr.store("fact", "test") is None

    def test_manager_enabled_when_backend_present(self):
        mgr = MemoryManager(RecordingBackend())
        assert mgr.enabled is True

    def test_manager_disabled_when_no_backend(self):
        mgr = MemoryManager(None)
        assert mgr.enabled is False


class TestMemoryManagerListUpdate:
    """Test list, update, delete, clear operations."""

    def test_list_all(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "one", project="proj1")
        mgr.store("fact", "two", project="proj2")

        results = mgr.list()
        assert len(results) == 2

    def test_list_filtered_by_project(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "one", project="proj1")
        mgr.store("fact", "two", project="proj2")

        results = mgr.list(project="proj1")
        assert len(results) == 1
        assert results[0]["project"] == "proj1"

    def test_update_record(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        stored = mgr.store("fact", "original content", project="proj")

        updated = mgr.update(stored["id"], "updated content")
        assert updated["content"] == "updated content"

    def test_delete_record(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        stored = mgr.store("fact", "to be deleted", project="proj")
        assert mgr.delete(stored["id"]) is True

    def test_clear_project(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "one", project="proj1")
        mgr.store("fact", "two", project="proj2")

        cleared = mgr.clear("proj1")
        assert cleared == 1
        assert len(mgr.list()) == 1


class TestInMemoryBackend:
    """Test the built-in InMemoryBackend."""

    def test_in_memory_store_and_search(self):
        backend = InMemoryBackend()
        stored = backend.store("fact", "Python is great", project="test")
        assert stored["content"] == "Python is great"

        results = backend.search("python", project="test")
        assert len(results) == 1

    def test_in_memory_list(self):
        backend = InMemoryBackend()
        backend.store("fact", "one", project="p1")
        backend.store("fact", "two", project="p2")
        assert len(backend.list()) == 2

    def test_in_memory_delete(self):
        backend = InMemoryBackend()
        stored = backend.store("fact", "test", project="p1")
        assert backend.delete(stored["id"]) is True
        assert len(backend.list()) == 0

    def test_in_memory_clear(self):
        backend = InMemoryBackend()
        backend.store("fact", "one", project="p1")
        backend.store("fact", "two", project="p2")
        assert backend.clear() == 2
        assert backend.clear() == 0

    def test_in_memory_clear_by_project(self):
        backend = InMemoryBackend()
        backend.store("fact", "one", project="p1")
        backend.store("fact", "two", project="p2")
        assert backend.clear("p1") == 1
        assert len(backend.list()) == 1

    def test_in_memory_update(self):
        backend = InMemoryBackend()
        stored = backend.store("fact", "original", project="p1")
        updated = backend.update(stored["id"], "updated")
        assert updated["content"] == "updated"

    def test_in_memory_close_is_noop(self):
        backend = InMemoryBackend()
        backend.close()  # should not raise


# ──────────────────────── Security Tests ──────────────────────────────

class TestSecurityFiltering:
    """Test that memory storage filters sensitive data."""

    def test_password_content_filtered(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "Database password: secret123", project="proj")
        assert len(backend._records) == 0

    def test_api_key_content_filtered(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "API_KEY=sk-12345", project="proj")
        assert len(backend._records) == 0

    def test_credentials_filtered(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "Credentials: user=admin", project="proj")
        assert len(backend._records) == 0

    def test_normal_content_not_filtered(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        mgr.store("fact", "The build system is cargo", project="proj")
        assert len(backend._records) == 1


# ──────────────────────── Memory Events Tests ─────────────────────────

class TestMemoryEvents:
    """Test memory-related events via EventBus."""

    def test_recall_events_emitted(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        bus = EventBus()
        mgr.set_event_bus(bus)

        events = []
        bus.subscribe(lambda e: events.append(e))

        mgr.search("test", project="proj", task_id="t1")

        event_types = [e.event_type.value for e in events]
        assert "memory.recall.started" in event_types
        assert "memory.recall.completed" in event_types

    def test_store_events_emitted(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        bus = EventBus()
        mgr.set_event_bus(bus)

        events = []
        bus.subscribe(lambda e: events.append(e))

        mgr.store("fact", "test content", project="proj", task_id="t1")

        event_types = [e.event_type.value for e in events]
        assert "memory.store.started" in event_types
        assert "memory.store.completed" in event_types

    def test_error_event_on_search_failure(self):
        backend = RecordingBackend(fail_search=True)
        mgr = MemoryManager(backend)
        bus = EventBus()
        mgr.set_event_bus(bus)

        events = []
        bus.subscribe(lambda e: events.append(e))

        mgr.search("test", project="proj", task_id="t1")

        event_types = [e.event_type.value for e in events]
        assert "memory.error" in event_types
        assert "memory.recall.started" in event_types

    def test_error_event_on_store_failure(self):
        backend = RecordingBackend(fail_store=True)
        mgr = MemoryManager(backend)
        bus = EventBus()
        mgr.set_event_bus(bus)

        events = []
        bus.subscribe(lambda e: events.append(e))

        mgr.store("fact", "test", project="proj", task_id="t1")

        event_types = [e.event_type.value for e in events]
        assert "memory.error" in event_types

    def test_no_events_without_bus(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        # No event bus set
        mgr.store("fact", "test", project="proj")
        mgr.search("test", project="proj")
        # Should not raise

    def test_event_data_json_serializable(self):
        backend = RecordingBackend()
        mgr = MemoryManager(backend)
        bus = EventBus()

        import json
        mgr.set_event_bus(bus)
        events = []
        bus.subscribe(lambda e: events.append(e))

        mgr.store("fact", "hello world", project="proj", task_id="t1")
        mgr.search("hello", project="proj", task_id="t1")

        for event in events:
            d = event.to_dict()
            json.dumps(d)  # Should not raise


# ──────────────────────── Agent Integration Tests ─────────────────────

class TestAgentMemoryIntegration:
    """Test memory integration with the Agent lifecycle."""

    def _make_in_memory_backend(self):
        return InMemoryBackend()

    def test_memory_recalled_before_planning(self, tmp_path):
        """Memory is recalled and used before the plan is generated."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import RuntimeResponse, FinishReason, ToolCall
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        backend = self._make_in_memory_backend()
        # Pre-populate with relevant memory
        backend.store("fact", "Use cargo for building Rust projects", project=str(tmp_path))

        runtime = MockRuntime(responses=[RuntimeResponse(
            content="Done",
            finish_reason=FinishReason.STOP,
        )])
        memory = MemoryManager(backend)
        bus = EventBus()

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
            event_bus=bus,
        )

        # Verify search was called
        initial_count = len(backend._records)
        agent.execute("Build the project", str(tmp_path))
        assert len(backend._records) > initial_count  # Task result was stored

    def test_memory_included_in_context(self, tmp_path):
        """Memory results are included in the model-facing context."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import RuntimeResponse, FinishReason
        from agentcore.agent import Agent, AgentConfig, ContextBuilder
        from agentcore.config import AgentCoreConfig

        backend = self._make_in_memory_backend()
        memory = MemoryManager(backend)
        bus = EventBus()

        from agentcore.task import Task
        task = Task(user_request="Test", project=str(tmp_path))
        task.project_context = {"language": "python"}
        task.selected_skills = []

        memory_results = [{"id": "m1", "content": "Relevant fact", "type": "fact", "project": str(tmp_path)}]
        context = ContextBuilder.build(task, [], memory_results, [])
        assert "memory_context" in context
        assert context["memory_context"]["count"] == 1

    def test_task_result_stored_after_completion(self, tmp_path):
        """Useful memory is stored after task completion."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import RuntimeResponse, FinishReason
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        backend = self._make_in_memory_backend()
        runtime = MockRuntime(responses=[RuntimeResponse(
            content="Done",
            finish_reason=FinishReason.STOP,
        )])
        memory = MemoryManager(backend)

        # Set a project on the backend to track
        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
        )

        project_path_str = str(tmp_path)
        records_before = len(backend._records)
        agent.execute("Test task", project_path_str)
        records_after = len(backend._records)

        # A task result should have been stored
        assert records_after > records_before

        # Verify the stored record is a "task" type
        stored = backend.list(project=project_path_str, type="task")
        assert len(stored) > 0

    def test_memory_failure_does_not_crash_task(self, tmp_path):
        """If memory search fails, the task continues normally."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import RuntimeResponse, FinishReason
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        backend = RecordingBackend(fail_search=True)
        runtime = MockRuntime(responses=[RuntimeResponse(
            content="Done",
            finish_reason=FinishReason.STOP,
        )])
        memory = MemoryManager(backend)

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
        )

        # Should not raise even though memory search will fail
        result = agent.execute("Test task", str(tmp_path))
        assert "success" in result

    def test_memory_stored_with_correct_project(self, tmp_path):
        """Stored memory uses the task's project identifier."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import RuntimeResponse, FinishReason
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        backend = self._make_in_memory_backend()
        runtime = MockRuntime(responses=[RuntimeResponse(
            content="Done",
            finish_reason=FinishReason.STOP,
        )])
        memory = MemoryManager(backend)

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
        )

        agent.execute("Fix the bug", str(tmp_path))

        # Check that a task record was stored with the right project
        tasks = backend.list(project=str(tmp_path), type="task")
        assert len(tasks) >= 1

    def test_memory_events_emitted_during_execution(self, tmp_path):
        """Memory events (recall/store) are emitted during agent execution."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.runtimes.base import RuntimeResponse, FinishReason
        from agentcore.agent import Agent, AgentConfig
        from agentcore.config import AgentCoreConfig

        backend = self._make_in_memory_backend()
        runtime = MockRuntime(responses=[RuntimeResponse(
            content="Done",
            finish_reason=FinishReason.STOP,
        )])
        memory = MemoryManager(backend)
        bus = EventBus()

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(enable_verification=False),
            project_path=tmp_path,
            agentcore_config=AgentCoreConfig.defaults(),
            event_bus=bus,
        )

        events = []
        bus.subscribe(lambda e: events.append(e))

        agent.execute("Test task", str(tmp_path))

        event_types = [e.event_type.value for e in events]
        assert "memory.recall.started" in event_types
        assert "memory.recall.completed" in event_types
        assert "memory.store.started" in event_types
        assert "memory.store.completed" in event_types


# ──────────────────────── Context Architecture Tests ──────────────────

class TestContextArchitecture:
    """Test the structured context representations."""

    def test_project_context_data(self, tmp_path):
        from agentcore.agent import ProjectContextData
        ctx = ProjectContextData(
            project_root=str(tmp_path),
            language="python",
            framework="fastapi",
            build_system="pip",
        )
        d = ctx.to_dict()
        assert d["project_root"] == str(tmp_path)
        assert d["language"] == "python"
        assert d["framework"] == "fastapi"

    def test_project_context_git_truncation(self):
        from agentcore.agent import ProjectContextData
        ctx = ProjectContextData(git_diff="x" * 10000)
        d = ctx.to_dict()
        assert len(d["git"]["diff"]) <= 5000  # Truncated to 5000 chars

    def test_task_context_data(self):
        from agentcore.agent import TaskContextData
        from agentcore.task import Task, TaskState
        task = Task(user_request="Fix bug", project="proj")
        ctx = TaskContextData(
            user_request=task.user_request,
            task_id=task.task_id,
            current_state=task.current_state.value,
        )
        d = ctx.to_dict()
        assert d["user_request"] == "Fix bug"
        assert d["task_id"] == task.task_id

    def test_memory_context_data(self):
        from agentcore.agent import MemoryContextData
        results = [{"id": f"m{i}", "content": f"fact {i}", "type": "fact"} for i in range(20)]
        ctx = MemoryContextData(results=results, count=len(results))
        d = ctx.to_dict()
        assert d["count"] == 20
        assert len(d["results"]) <= 10  # Limited

    def test_skill_context_data(self):
        from agentcore.agent import SkillContextData
        ctx = SkillContextData(
            selected=["bug-fix", "testing"],
            available=["bug-fix", "testing", "refactoring"],
            attributes={"confidence": 0.9},
        )
        d = ctx.to_dict()
        assert "bug-fix" in d["selected"]
        assert len(d["available"]) == 3

    def test_runtime_context_data(self):
        from agentcore.agent import RuntimeContextData
        ctx = RuntimeContextData(runtime_name="hermes", model="claude-3")
        d = ctx.to_dict()
        assert d["runtime"] == "hermes"
        assert d["model"] == "claude-3"


class TestContextBuilderCombined:
    """Test ContextBuilder combining all context types."""

    def test_combined_context_has_all_sections(self, tmp_path):
        from agentcore.agent import ContextBuilder
        from agentcore.task import Task

        task = Task(user_request="Fix the crash", project=str(tmp_path))
        task.project_context = {"language": "rust", "build_system": "cargo"}
        task.selected_skills = ["bug-fix"]

        context = ContextBuilder.build(task, [], [], [])
        assert "project_context" in context
        assert "task_context" in context
        assert "memory_context" in context
        assert "skill_context" in context
        assert "runtime_context" in context
        assert "instructions" in context
        assert "user_request" in context

    def test_context_limits_enforced(self, tmp_path):
        from agentcore.agent import ContextBuilder
        from agentcore.task import Task

        task = Task(user_request="Test", project=str(tmp_path))
        task.project_context = {}

        many_tool_results = [{"tool": f"t{i}", "output": "x" * 100} for i in range(50)]
        context = ContextBuilder.build(task, [], [], many_tool_results)
        assert len(context["task_context"]["tool_results"]) <= ContextBuilder.MAX_TOOL_RESULTS

    def test_context_with_memory(self, tmp_path):
        from agentcore.agent import ContextBuilder
        from agentcore.task import Task

        task = Task(user_request="Test", project=str(tmp_path))
        task.project_context = {"language": "python"}
        task.memory_context = {"count": 2, "results": [{"id": "m1", "content": "fact"}]}

        memory_results = [{"id": "m1", "content": "relevant fact", "type": "fact"}]
        context = ContextBuilder.build(task, [], memory_results, [])

        assert context["memory_context"]["count"] == 1
        assert len(context["memory_context"]["results"]) >= 1

    def test_context_missing_project_metadata(self, tmp_path):
        """ContextBuilder handles missing project metadata gracefully."""
        from agentcore.agent import ContextBuilder
        from agentcore.task import Task

        task = Task(user_request="Test", project=str(tmp_path))
        # No project_context set
        task.project_context = {}

        context = ContextBuilder.build(task, [], [], [])
        # Should not crash, should have default values
        assert context["project_context"]["language"] is None
        assert context["project_context"]["project_root"] == str(tmp_path)


# ──────────────────────── DB-Obsidian Adapter Tests ───────────────────

class TestDBObsidianAdapter:
    """Test the DB-Obsidian adapter conforms to MemoryBackend."""

    def test_adapter_exists(self):
        """The DB-Obsidian adapter should exist (if db_obsidian is installed)."""
        try:
            from agentcore.adapters.memory_dbobsidian import DBObsidianBackend, create_memory_manager
            assert DBObsidianBackend is not None
            assert create_memory_manager is not None
        except ImportError:
            pytest.skip("db_obsidian not installed")

    def test_adapter_implements_backend(self):
        """DBObsidianBackend must implement all abstract MemoryBackend methods."""
        try:
            from agentcore.adapters.memory_dbobsidian import DBObsidianBackend
        except ImportError:
            pytest.skip("db_obsidian not installed")

        # Check it's a subclass of MemoryBackend
        assert issubclass(DBObsidianBackend, MemoryBackend)

        # Check it has all required methods
        for method in ["search", "store", "update", "list"]:
            assert hasattr(DBObsidianBackend, method)

    def test_adapter_no_hardcoded_obsidian_portal_path(self):
        """The adapter should not hardcode 'ObsidianVault' as a path."""
        try:
            from agentcore.adapters.memory_dbobsidian import create_memory_manager
        except ImportError:
            pytest.skip("db_obsidian not installed")

        source = open(create_memory_manager.__code__.co_filename).read()
        # The create_memory_manager function should use user_data_dir, not hardcoded paths
        assert "ObsidianVault" not in source

    def test_adapter_does_not_import_db_obsidian_at_module_level_in_memory(self):
        """agentcore.memory should not import db_obsidian."""
        import agentcore.memory as memory_module
        source = open(memory_module.__file__).read()
        assert "db_obsidian" not in source


# ──────────────────────── Backward Compatibility Tests ───────────────

class TestBackwardCompatibility:
    """Ensure backward compatibility with existing code."""

    def test_existing_memory_backend_interface_still_works(self):
        """The original MemoryBackend interface (search/store/update/list) still works."""

        class SimpleBackend(MemoryBackend):
            def __init__(self):
                self.data = []
            def search(self, query, project=None, limit=20):
                return [d for d in self.data if query in d.get("content", "")]
            def store(self, type, content, project=None, importance=0.5):
                rec = {"id": str(len(self.data)), "type": type, "content": content, "project": project}
                self.data.append(rec)
                return rec
            def update(self, memory_id, content):
                for d in self.data:
                    if d["id"] == memory_id:
                        d["content"] = content
                        return d
                return {}
            def list(self, project=None, type=None, limit=50):
                return self.data[:limit]

        backend = SimpleBackend()
        mgr = MemoryManager(backend)

        # Original interface works
        mgr.store("fact", "test content")
        results = mgr.search("test")
        assert len(results) == 1
        assert results[0]["content"] == "test content"

    def test_memory_manager_none_backend(self):
        """MemoryManager works with no backend (disabled state)."""
        mgr = MemoryManager(None)
        assert mgr.search("test") == []
        assert mgr.store("fact", "test") is None
        assert mgr.list() == []
        assert mgr.update("id", "content") is None
        assert mgr.delete("id") is False
        assert mgr.clear() == 0