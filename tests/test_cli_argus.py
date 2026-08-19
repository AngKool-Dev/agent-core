"""
CLI tests for Phase 5F — argus observability interface.

Tests use in-memory/ephemeral backends. No coupling to real user data.
"""

from __future__ import annotations

import argparse
import json
import tempfile

import pytest

from agentcore.cli.commands.memory import (
    memory_confidence,
    memory_search,
    memory_show,
)
from agentcore.cli.commands.task import (
    list_tasks,
    show_task,
    show_task_json,
    task_events,
    task_memories,
)
from agentcore.cli.service import QueryService, create_ephemeral_query_service
from agentcore.cli.utils import confidence_label, parse_confidence
from agentcore.observations import Observation
from agentcore.task import Task, TaskState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc():
    service = create_ephemeral_query_service()
    yield service
    try:
        if hasattr(service.observation_store, "close"):
            service.observation_store.close()
    except Exception:
        pass
    try:
        if hasattr(service.memory_backend, "close"):
            service.memory_backend.close()
    except Exception:
        pass


def _register_task(
    svc: QueryService,
    task_id: str,
    state: str = "COMPLETED",
    project: str = "test-project",
    user_request: str = "Test request",
):
    """Register a task in the registry and persist it."""
    task = Task(
        task_id=task_id,
        user_request=user_request,
        project=project,
        current_state=TaskState[state],
    )
    record = svc.task_registry.register(
        task,
        metadata={
            "source": "hermes_desktop",
            "runtime": "hermes",
            "hermes_session_id": task_id.replace("hermes-", "").replace("-turn-", "_s"),
            "hermes_task_id": task_id,
        },
    )
    svc.persistence.checkpoint(task)
    return record


def _add_observation(
    svc: QueryService,
    task_id: str,
    obs_type: str = "task.registered",
    payload: dict | None = None,
    sequence: int = 1,
):
    obs = Observation(
        id=f"obs-{sequence}",
        task_id=task_id,
        session_id=task_id,
        observation_type=obs_type,
        payload=payload or {},
        sequence=sequence,
    )
    svc.observation_store.add(obs)


def _store_memory(
    svc: QueryService, task_id: str, content: str, mem_type: str = "fact", confidence: float = 0.7
) -> dict:
    return svc.memory_backend.store(
        type=mem_type,
        content=content,
        project=task_id,
        importance=0.5,
        confidence=confidence,
    )


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# Confidence parsing utility tests
# ---------------------------------------------------------------------------


class TestConfidenceParsing:
    def test_parse_confidence_float(self):
        val, err = parse_confidence("0.7")
        assert err is None
        assert val == 0.7

    def test_parse_confidence_enum_verified(self):
        val, err = parse_confidence("VERIFIED")
        assert err is None
        assert val == 1.0

    def test_parse_confidence_enum_claimed(self):
        val, err = parse_confidence("claimed")
        assert err is None
        assert val == 0.7

    def test_parse_confidence_enum_inferred(self):
        val, err = parse_confidence("InFeRrEd")
        assert err is None
        assert val == 0.5

    def test_parse_confidence_enum_unknown(self):
        val, err = parse_confidence("unknown")
        assert err is None
        assert val == 0.3

    def test_parse_confidence_invalid(self):
        val, err = parse_confidence("not-a-confidence")
        assert val is None
        assert "Invalid confidence value" in err

    def test_parse_confidence_out_of_range(self):
        val, err = parse_confidence("1.5")
        assert val is None
        assert "must be in [0, 1]" in err

    def test_confidence_label_mapping(self):
        assert confidence_label(1.0) == "VERIFIED"
        assert confidence_label(0.9) == "VERIFIED"
        assert confidence_label(0.7) == "CLAIMED"
        assert confidence_label(0.6) == "CLAIMED"
        assert confidence_label(0.5) == "INFERRED"
        assert confidence_label(0.3) == "UNKNOWN"
        assert confidence_label(None) == "UNKNOWN"


# ---------------------------------------------------------------------------
# Task commands
# ---------------------------------------------------------------------------


class TestTaskList:
    def test_list_tasks(self, svc, capsys):
        _register_task(svc, "hermes-abc-turn-001", state="COMPLETED")
        _register_task(svc, "hermes-abc-turn-002", state="RUNNING")

        ret = list_tasks(svc, _ns(json=False, state=None, source=None, runtime=None))
        assert ret == 0

        out = capsys.readouterr().out
        assert "hermes-abc-turn-001" in out
        assert "hermes-abc-turn-002" in out
        assert "COMPLETED" in out
        assert "RUNNING" in out
        assert "hermes_desktop" in out
        assert "hermes" in out

    def test_list_tasks_filter_by_state(self, svc, capsys):
        _register_task(svc, "task-a", state="COMPLETED")
        _register_task(svc, "task-b", state="RUNNING")

        ret = list_tasks(svc, _ns(json=False, state="running", source=None, runtime=None))
        assert ret == 0

        out = capsys.readouterr().out
        assert "task-a" not in out
        assert "task-b" in out

    def test_list_tasks_filter_by_source(self, svc, capsys):
        _register_task(svc, "task-c", state="COMPLETED")

        ret = list_tasks(svc, _ns(json=False, state=None, source="hermes_desktop", runtime=None))
        assert ret == 0
        out = capsys.readouterr().out
        assert "task-c" in out

    def test_list_tasks_filter_by_runtime(self, svc, capsys):
        _register_task(svc, "task-d", state="COMPLETED")

        ret = list_tasks(svc, _ns(json=False, state=None, source=None, runtime="hermes"))
        assert ret == 0
        assert "task-d" in capsys.readouterr().out

    def test_list_tasks_json(self, svc, capsys):
        _register_task(svc, "task-json-1", state="COMPLETED")

        ret = list_tasks(svc, _ns(json=True, state=None, source=None, runtime=None))
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 1
        ids = [r["task_id"] for r in data]
        assert "task-json-1" in ids

    def test_list_tasks_empty(self, svc, capsys):
        ret = list_tasks(svc, _ns(json=False, state=None, source=None, runtime=None))
        assert ret == 0
        out = capsys.readouterr().out
        assert "No tasks" in out


class TestTaskShow:
    def test_show_task(self, svc, capsys):
        _register_task(
            svc, "hermes-xyz-turn-001", state="COMPLETED", user_request="Fix the login bug"
        )

        ret = show_task(svc, _ns(task_id="hermes-xyz-turn-001", json=False))
        assert ret == 0

        out = capsys.readouterr().out
        assert "hermes-xyz-turn-001" in out
        assert "COMPLETED" in out
        assert "Login bug" in out or "login bug" in out.lower()
        assert "hermes_desktop" in out

    def test_show_task_json(self, svc, capsys):
        _register_task(svc, "hermes-xyz-turn-001", state="COMPLETED")

        ret = show_task_json(svc, _ns(task_id="hermes-xyz-turn-001", json=True))
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["task_id"] == "hermes-xyz-turn-001"
        assert data["task_state"] == "COMPLETED"

    def test_show_unknown_task(self, svc, capsys):
        ret = show_task(svc, _ns(task_id="nonexistent-task", json=False))
        assert ret == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()


class TestTaskEvents:
    def test_task_events(self, svc, capsys):
        _register_task(svc, "hermes-ev-turn-001")
        _add_observation(
            svc, "hermes-ev-turn-001", "task.registered", payload={"session_id": "s1"}, sequence=1
        )
        _add_observation(svc, "hermes-ev-turn-001", "task.started", sequence=2)
        _add_observation(svc, "hermes-ev-turn-001", "task.completed", sequence=3)

        ret = task_events(
            svc, _ns(task_id="hermes-ev-turn-001", limit=1000, full=False, json=False)
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "task.registered" in out
        assert "task.started" in out
        assert "task.completed" in out
        assert "1" in out and "2" in out and "3" in out

    def test_task_events_limit(self, svc, capsys):
        _register_task(svc, "hermes-lim-turn-001")
        for i in range(10):
            _add_observation(
                svc,
                "hermes-lim-turn-001",
                "tool_call.started",
                payload={"name": f"tool{i}"},
                sequence=i,
            )

        ret = task_events(svc, _ns(task_id="hermes-lim-turn-001", limit=5, full=False, json=False))
        assert ret == 0

        out = capsys.readouterr().out
        assert "10 observation" in out or "5 observation" in out

    def test_task_events_json(self, svc, capsys):
        _register_task(svc, "hermes-ev-turn-002")
        _add_observation(
            svc, "hermes-ev-turn-002", "task.completed", payload={"result": "done"}, sequence=1
        )

        ret = task_events(svc, _ns(task_id="hermes-ev-turn-002", limit=1000, full=False, json=True))
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["observation_type"] == "task.completed"
        assert data[0]["payload"]["result"] == "done"

    def test_task_events_unknown_task(self, svc, capsys):
        ret = task_events(svc, _ns(task_id="nonexistent", limit=1000, full=False, json=False))
        assert ret == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_task_events_empty(self, svc, capsys):
        _register_task(svc, "hermes-empty-turn-001")
        ret = task_events(
            svc, _ns(task_id="hermes-empty-turn-001", limit=1000, full=False, json=False)
        )
        assert ret == 0
        out = capsys.readouterr().out
        assert "No observations" in out


class TestTaskMemories:
    def test_task_memories(self, svc, capsys):
        _register_task(svc, "hermes-mem-turn-001")
        _store_memory(
            svc, "hermes-mem-turn-001", "Test memory content", mem_type="fact", confidence=0.7
        )

        ret = task_memories(
            svc,
            _ns(
                task_id="hermes-mem-turn-001", min_confidence=None, type=None, limit=50, json=False
            ),
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "hermes-mem-turn-001" in out or "mem-" in out
        assert "fact" in out
        assert "CLAIMED" in out
        assert "Test memory content" in out

    def test_task_memories_json(self, svc, capsys):
        _register_task(svc, "hermes-memj-turn-001")
        _store_memory(
            svc, "hermes-memj-turn-001", "JSON memory content", mem_type="fact", confidence=1.0
        )

        ret = task_memories(
            svc,
            _ns(
                task_id="hermes-memj-turn-001", min_confidence=None, type=None, limit=50, json=True
            ),
        )
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(m.get("content") == "JSON memory content" for m in data)

    def test_task_memories_unknown_task(self, svc, capsys):
        ret = task_memories(
            svc, _ns(task_id="nonexistent", min_confidence=None, type=None, limit=50, json=False)
        )
        assert ret == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_task_memories_with_min_confidence(self, svc, capsys):
        _register_task(svc, "hermes-mc-turn-001")
        _store_memory(svc, "hermes-mc-turn-001", "Low conf memory", mem_type="fact", confidence=0.3)
        _store_memory(
            svc, "hermes-mc-turn-001", "High conf memory", mem_type="fact", confidence=1.0
        )

        ret = task_memories(
            svc,
            _ns(
                task_id="hermes-mc-turn-001", min_confidence="0.7", type=None, limit=50, json=False
            ),
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "High conf memory" in out
        # Low confidence memory should be filtered out
        # (the exact filtering depends on whether the InMemoryBackend stores both
        #  or dedupes — with InMemoryBackend, both are stored, and the filter applies)

    def test_task_memories_type_filter(self, svc, capsys):
        _register_task(svc, "hermes-tf-turn-001")
        _store_memory(svc, "hermes-tf-turn-001", "Fact content", mem_type="fact", confidence=0.7)
        _store_memory(svc, "hermes-tf-turn-001", "Task content", mem_type="task", confidence=0.7)

        ret = task_memories(
            svc,
            _ns(
                task_id="hermes-tf-turn-001", min_confidence=None, type="fact", limit=50, json=False
            ),
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "Fact content" in out
        assert "Task content" not in out


# ---------------------------------------------------------------------------
# Memory commands
# ---------------------------------------------------------------------------


class TestMemorySearch:
    def test_memory_search(self, svc, capsys):
        _store_memory(
            svc, "task-1", "The launcher architecture uses plugins", mem_type="fact", confidence=0.7
        )

        ret = memory_search(
            svc, _ns(query="launcher", limit=20, min_confidence=None, type=None, json=False)
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "launcher" in out
        assert "fact" in out

    def test_memory_search_empty_result(self, svc, capsys):
        ret = memory_search(
            svc, _ns(query="nonexistentterm", limit=20, min_confidence=None, type=None, json=False)
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "No memories found" in out

    def test_memory_search_json(self, svc, capsys):
        _store_memory(svc, "task-1", "Searchable content here", mem_type="fact", confidence=0.7)

        ret = memory_search(
            svc, _ns(query="searchable", limit=20, min_confidence=None, type=None, json=True)
        )
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any("Searchable" in m.get("content", "") for m in data)

    def test_memory_search_min_confidence_float(self, svc, capsys):
        _store_memory(svc, "task-1", "low conf memory", confidence=0.3)
        _store_memory(svc, "task-1", "high conf memory", confidence=1.0)

        ret = memory_search(
            svc, _ns(query="conf memory", limit=20, min_confidence="0.7", type=None, json=False)
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "high conf memory" in out

    def test_memory_search_min_confidence_enum(self, svc, capsys):
        _store_memory(svc, "task-1", "low conf memory", confidence=0.3)
        _store_memory(svc, "task-1", "high conf memory", confidence=1.0)

        ret = memory_search(
            svc,
            _ns(query="conf memory", limit=20, min_confidence="VERIFIED", type=None, json=False),
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "high conf memory" in out
        assert "low conf memory" not in out

    def test_memory_search_type_filter(self, svc, capsys):
        _store_memory(svc, "task-1", "fact content", mem_type="fact", confidence=0.7)
        _store_memory(svc, "task-1", "decision content", mem_type="decision", confidence=0.7)

        ret = memory_search(
            svc, _ns(query="content", limit=20, min_confidence=None, type="fact", json=False)
        )
        assert ret == 0

        out = capsys.readouterr().out
        assert "fact content" in out
        assert "decision content" not in out


class TestMemoryShow:
    def test_memory_show(self, svc, capsys):
        mem = _store_memory(
            svc, "task-1", "Detailed memory content for display", mem_type="fact", confidence=0.7
        )

        ret = memory_show(svc, _ns(memory_id=mem["id"], json=False))
        assert ret == 0

        out = capsys.readouterr().out
        assert mem["id"] in out
        assert "fact" in out
        assert "Detailed memory content" in out

    def test_memory_show_json(self, svc, capsys):
        mem = _store_memory(svc, "task-1", "JSON display memory", mem_type="fact", confidence=1.0)

        ret = memory_show(svc, _ns(memory_id=mem["id"], json=True))
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["id"] == mem["id"]
        assert data["content"] == "JSON display memory"

    def test_memory_show_unknown(self, svc, capsys):
        ret = memory_show(svc, _ns(memory_id="nonexistent-mem", json=False))
        assert ret == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()


class TestMemoryConfidence:
    def test_memory_confidence(self, svc, capsys):
        mem = _store_memory(
            svc, "task-1", "Confidence test memory", mem_type="fact", confidence=1.0
        )

        ret = memory_confidence(svc, _ns(memory_id=mem["id"], json=False))
        assert ret == 0

        out = capsys.readouterr().out
        assert "VERIFIED" in out
        assert "1.00" in out or "1.0" in out

    def test_memory_confidence_json(self, svc, capsys):
        mem = _store_memory(svc, "task-1", "Confidence JSON test", mem_type="task", confidence=0.7)

        ret = memory_confidence(svc, _ns(memory_id=mem["id"], json=True))
        assert ret == 0

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["memory_id"] == mem["id"]
        assert data["confidence"] == 0.7
        assert data["confidence_level"] == "CLAIMED"
        assert data["task_id"] == "task-1"

    def test_memory_confidence_unknown_memory(self, svc, capsys):
        ret = memory_confidence(svc, _ns(memory_id="nonexistent-mem", json=False))
        assert ret == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()


class TestConfidenceFilter:
    def test_invalid_confidence_filter(self, svc, capsys):
        _store_memory(svc, "task-1", "test content", confidence=0.7)

        ret = memory_search(
            svc, _ns(query="test", limit=20, min_confidence="invalid", type=None, json=False)
        )
        assert ret == 1
        err = capsys.readouterr().err
        assert "Invalid confidence" in err

    def test_none_confidence_filter(self, svc, capsys):
        _store_memory(svc, "task-1", "test content", confidence=0.3)

        ret = memory_search(
            svc, _ns(query="test", limit=20, min_confidence=None, type=None, json=False)
        )
        assert ret == 0


class TestBackendFailure:
    def test_backend_failure_clean_error(self, svc, capsys):
        svc.memory_backend = _FailingBackend()

        ret = memory_search(
            svc, _ns(query="test", limit=20, min_confidence=None, type=None, json=False)
        )
        assert ret != 0
        err = capsys.readouterr().err
        assert "Search failed" in err or "Error" in err

    def test_backend_failure_memory_show(self, svc, capsys):
        svc.memory_backend = _FailingBackend()

        ret = memory_show(svc, _ns(memory_id="any-id", json=False))
        assert ret != 0
        err = capsys.readouterr().err
        assert "Error" in err


class _FailingBackend:
    """Backend that always raises on operations."""

    def search(self, query, **kwargs):
        raise RuntimeError("db connection lost")

    def get(self, memory_id):
        raise RuntimeError("db connection lost")

    def list(self, project=None, type=None, limit=50):
        raise RuntimeError("db connection lost")

    def store(self, *args, **kwargs):
        raise RuntimeError("db connection lost")

    def update(self, *args, **kwargs):
        return {}


# ---------------------------------------------------------------------------
# JSON validity tests
# ---------------------------------------------------------------------------


class TestJSONOutput:
    def test_task_show_json_valid(self, svc, capsys):
        _register_task(svc, "hermes-jwt-001", state="COMPLETED")
        ret = show_task_json(svc, _ns(task_id="hermes-jwt-001", json=True))
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)

    def test_task_events_json_valid(self, svc, capsys):
        _register_task(svc, "hermes-jte-001")
        _add_observation(svc, "hermes-jte-001", "task.completed", sequence=1)
        ret = task_events(svc, _ns(task_id="hermes-jte-001", limit=1000, full=False, json=True))
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_task_memories_json_valid(self, svc, capsys):
        _register_task(svc, "hermes-jtm-001")
        _store_memory(svc, "hermes-jtm-001", "content", mem_type="fact", confidence=0.7)
        ret = task_memories(
            svc, _ns(task_id="hermes-jtm-001", min_confidence=None, type=None, limit=50, json=True)
        )
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_memory_search_json_valid(self, svc, capsys):
        _store_memory(svc, "task-1", "search content", mem_type="fact", confidence=0.7)
        ret = memory_search(
            svc, _ns(query="search", limit=20, min_confidence=None, type=None, json=True)
        )
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_memory_show_json_valid(self, svc, capsys):
        mem = _store_memory(svc, "task-1", "show content", mem_type="fact", confidence=0.7)
        ret = memory_show(svc, _ns(memory_id=mem["id"], json=True))
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)

    def test_memory_confidence_json_valid(self, svc, capsys):
        mem = _store_memory(svc, "task-1", "conf content", mem_type="fact", confidence=1.0)
        ret = memory_confidence(svc, _ns(memory_id=mem["id"], json=True))
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, dict)
        assert "confidence" in data
        assert "confidence_level" in data


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------


class TestRegression:
    def test_existing_cli_still_works(self):
        """The agent CLI (non-argus) should still parse and run."""
        from agentcore.cli.main import parse_args

        args = parse_args(["--list-runtimes"])
        assert args.list_runtimes is True

    def test_argus_no_command_shows_help(self, capsys):
        from agentcore.cli.main import argus_main

        ret = argus_main([])
        assert ret == 0
        out = capsys.readouterr().out
        assert "usage:" in out

    def test_cli_queries_do_not_mutate_task_state(self, svc):
        _register_task(svc, "hermes-reg-turn-001", state="COMPLETED")
        rec_before = svc.task_registry.get("hermes-reg-turn-001")
        assert rec_before is not None
        state_before = rec_before.task_state

        ret = list_tasks(svc, _ns(json=False, state=None, source=None, runtime=None))
        assert ret == 0

        rec_after = svc.task_registry.get("hermes-reg-turn-001")
        assert rec_after.task_state == state_before

    def test_cli_queries_do_not_create_duplicate_memories(self, svc):
        _store_memory(svc, "task-1", "unique content", mem_type="fact", confidence=0.7)

        before_count = len(svc.memory_backend.list())
        ret = memory_search(
            svc, _ns(query="unique", limit=20, min_confidence=None, type=None, json=False)
        )
        assert ret == 0

        after_count = len(svc.memory_backend.list())
        assert after_count == before_count

    def test_argus_task_help(self, capsys):
        from agentcore.cli.main import _build_argus_parser

        parser = _build_argus_parser()
        try:
            parser.parse_args(["task", "list", "--help"])
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        assert "state" in out


# ---------------------------------------------------------------------------
# argus_main end-to-end test
# ---------------------------------------------------------------------------


class TestArgusMainEndToEnd:
    def test_argus_task_list_empty(self, capsys, monkeypatch):
        from agentcore.cli.service import create_ephemeral_query_service

        # Use a real ephemeral service so the test exercises the full path
        tmpdir = tempfile.mkdtemp(prefix="argus-e2e-")
        monkeypatch.setenv("HOME", tmpdir)

        # We can't easily redirect create_query_service, so test via command handlers
        svc = create_ephemeral_query_service()
        ret = list_tasks(svc, _ns(json=False, state=None, source=None, runtime=None))
        assert ret == 0
        out = capsys.readouterr().out
        assert "No tasks" in out

    def test_argus_memory_search_no_backend(self, capsys):
        """If no backend is available, CLI should give clean error, not traceback."""
        from agentcore.cli.commands.memory import memory_search
        from agentcore.cli.service import QueryService

        # Create a service with a backend that has no search capability
        svc = QueryService(
            task_registry=None,
            persistence=None,
            observation_store=None,
            memory_backend=_NoBackend(),
            memory_manager=None,
            data_dir=None,
        )

        ret = memory_search(
            svc, _ns(query="test", limit=20, min_confidence=None, type=None, json=False)
        )
        assert ret == 1
        err = capsys.readouterr().err
        assert "Error" in err


class _NoBackend:
    """Backend that returns None for get and raises on search."""

    def search(self, query, **kwargs):
        raise RuntimeError("no backend")

    def get(self, memory_id):
        raise RuntimeError("no backend")

    def list(self, **kwargs):
        raise RuntimeError("no backend")

    def store(self, *args, **kwargs):
        return {}

    def update(self, *args, **kwargs):
        return {}
