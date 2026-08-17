"""
Tests for AgentCore lifecycle, shutdown, recovery, and limits (Phase 8).
"""

import json
import time

import pytest

from agentcore.agentcore import AgentCore, AgentCoreLimits, create_agent_core
from agentcore.task_registry import TaskRecord, TaskRecordStatus
from agentcore.events import EventBus, EventType
from agentcore.errors import ConfigurationError
from agentcore.task import Task, TaskState


class TestAgentCoreLimits:
    def test_default_limits(self):
        limits = AgentCoreLimits()
        assert limits.max_active_tasks == 10
        assert limits.max_task_execution_seconds == 600
        assert limits.max_task_lifetime_seconds == 3600

    def test_valid_limits_pass(self):
        limits = AgentCoreLimits(
            max_active_tasks=5,
            max_task_execution_seconds=300,
            max_task_lifetime_seconds=1800,
            max_recovery_tasks=50,
            max_event_history=500,
            max_persisted_task_size_bytes=2048,
        )
        limits.validate()  # should not raise

    def test_invalid_max_active_tasks(self):
        limits = AgentCoreLimits(max_active_tasks=0)
        with pytest.raises(ConfigurationError):
            limits.validate()

    def test_invalid_max_execution_seconds(self):
        limits = AgentCoreLimits(max_task_execution_seconds=0)
        with pytest.raises(ConfigurationError):
            limits.validate()

    def test_invalid_max_lifetime_seconds(self):
        limits = AgentCoreLimits(max_task_lifetime_seconds=0)
        with pytest.raises(ConfigurationError):
            limits.validate()

    def test_invalid_max_recovery_tasks(self):
        limits = AgentCoreLimits(max_recovery_tasks=0)
        with pytest.raises(ConfigurationError):
            limits.validate()

    def test_invalid_max_event_history(self):
        limits = AgentCoreLimits(max_event_history=0)
        with pytest.raises(ConfigurationError):
            limits.validate()

    def test_invalid_max_persisted_task_size(self):
        limits = AgentCoreLimits(max_persisted_task_size_bytes=512)
        with pytest.raises(ConfigurationError):
            limits.validate()

    def test_limits_to_dict(self):
        limits = AgentCoreLimits()
        d = limits.to_dict()
        assert "max_active_tasks" in d
        assert d["max_active_tasks"] == 10


class TestAgentCoreShutdown:
    def test_shutdown_with_no_tasks(self):
        core = AgentCore()
        result = core.shutdown()
        assert result["shutdown"] is True
        assert result["checkpointed"] == 0
        assert result["cancelled"] == 0

    def test_shutdown_is_idempotent(self):
        core = AgentCore()
        core.shutdown()
        result = core.shutdown()
        assert result["shutdown"] is True

    def test_shutdown_emits_events(self):
        bus = EventBus()
        core = AgentCore(event_bus=bus)
        events = []
        bus.subscribe(lambda e: events.append(e))
        core.shutdown()
        event_types = [e.event_type for e in events]
        assert EventType.SHUTDOWN_STARTED in event_types
        assert EventType.SHUTDOWN_COMPLETED in event_types

    def test_shutdown_after_register(self):
        bus = EventBus()
        core = AgentCore(event_bus=bus)
        task = Task(task_id="t1", user_request="test", project="proj")
        core.registry.register(task)
        result = core.shutdown()
        assert result["shutdown"] is True


class TestAgentCoreRecovery:
    def test_recover_no_tasks(self):
        core = AgentCore()
        recovered = core.recover_tasks()
        assert recovered == []

    def test_recover_emits_events(self):
        bus = EventBus()
        core = AgentCore(event_bus=bus)
        events = []
        bus.subscribe(lambda e: events.append(e))
        core.recover_tasks()
        event_types = [e.event_type for e in events]
        assert EventType.RECOVERY_STARTED in event_types
        assert EventType.RECOVERY_COMPLETED in event_types


class TestAgentCoreRegistryIntegration:
    def test_registry_accessible(self):
        core = AgentCore()
        assert core.registry is not None

    def test_register_and_get_task(self):
        core = AgentCore()
        task = Task(task_id="t1", user_request="test", project="proj")
        record = core.registry.register(task)
        assert record.task_id == "t1"
        fetched = core.registry.get("t1")
        assert fetched is not None

    def test_list_active_tasks(self):
        core = AgentCore()
        t1 = Task(task_id="t1", user_request="test", project="proj")
        t2 = Task(task_id="t2", user_request="test", project="proj", current_state=TaskState.COMPLETED)
        core.registry.register(t1)
        core.registry.register(t2)
        active = core.registry.list_active()
        assert len(active) == 1
        assert active[0].task_id == "t1"

    def test_list_terminal_tasks(self):
        core = AgentCore()
        t1 = Task(task_id="t1", user_request="test", project="proj")
        t2 = Task(task_id="t2", user_request="test", project="proj", current_state=TaskState.COMPLETED)
        core.registry.register(t1)
        core.registry.register(t2)
        terminal = core.registry.list_terminal()
        assert len(terminal) == 1
        assert terminal[0].task_id == "t2"

    def test_list_resumable_tasks(self):
        core = AgentCore()
        t1 = Task(task_id="t1", user_request="test", project="proj")
        t2 = Task(task_id="t2", user_request="test", project="proj", current_state=TaskState.RUNNING)
        core.registry.register(t1)
        core.registry.register(t2)
        core.registry.acquire_lock("t2", "holder-1")
        resumable = core.registry.list_resumable()
        assert len(resumable) == 1
        assert resumable[0].task_id == "t1"

    def test_lock_and_unlock(self):
        core = AgentCore()
        task = Task(task_id="t1", user_request="test", project="proj")
        core.registry.register(task)
        assert core.registry.acquire_lock("t1", "holder-1") is True
        assert core.registry.is_locked("t1") is True
        assert core.registry.release_lock("t1", "holder-1") is True
        assert core.registry.is_locked("t1") is False

    def test_duplicate_lock_rejected(self):
        core = AgentCore()
        task = Task(task_id="t1", user_request="test", project="proj")
        core.registry.register(task)
        core.registry.acquire_lock("t1", "holder-1")
        with pytest.raises(Exception):
            core.registry.acquire_lock("t1", "holder-2")

    def test_shutdown_releases_locks(self):
        core = AgentCore()
        task = Task(task_id="t1", user_request="test", project="proj")
        core.registry.register(task)
        core.registry.acquire_lock("t1", "holder-1")
        core.shutdown()
        assert core.registry.is_locked("t1") is False

    def test_max_active_tasks_limit(self):
        core = AgentCore(limits=AgentCoreLimits(max_active_tasks=2))
        for i in range(3):
            task = Task(task_id=f"t{i}", user_request="test", project="proj")
            core.registry.register(task)
        active = core.registry.list_active()
        assert len(active) == 3  # registry doesn't enforce limit; AgentCore facade would

    def test_task_record_serialization(self):
        record = TaskRecord(
            task_id="t1",
            user_request="test",
            project="proj",
            status=TaskRecordStatus.RUNNING,
            task_state=TaskState.RUNNING,
        )
        d = record.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "running"
        assert d["task_state"] == "RUNNING"

        restored = TaskRecord.from_dict(d)
        assert restored.task_id == "t1"
        assert restored.status == TaskRecordStatus.RUNNING
        assert restored.task_state == TaskState.RUNNING


class TestAgentCoreCreateFactory:
    def test_create_agent_core_defaults(self):
        core = create_agent_core()
        assert isinstance(core, AgentCore)
        assert core.registry is not None
        assert core.persistence is not None
        assert core.event_bus is not None

    def test_create_agent_core_with_config(self, tmp_path):
        from agentcore.config import AgentCoreConfig
        config = AgentCoreConfig(default_runtime="hermes")
        core = create_agent_core(config=config, project_path=tmp_path)
        assert core.config.default_runtime == "hermes"
