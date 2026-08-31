"""Tests for state management."""

import pytest
from unittest.mock import MagicMock

from argus.state import (
    AgentState,
    PlanStep,
    RunStatus,
    StateManager,
    StateSnapshot,
    StateStore,
    SnapshotManager,
)


class TestAgentState:
    def test_create_state(self):
        state = AgentState(task="test task")
        assert state.task == "test task"
        assert state.status == RunStatus.PENDING
        assert state.run_id is not None
        assert state.session_id is not None

    def test_add_plan_step(self):
        state = AgentState(task="test")
        step = state.add_plan_step("Do something", "cap1")
        assert len(state.plan) == 1
        assert step.description == "Do something"
        assert step.status == "pending"

    def test_set_step_status(self):
        state = AgentState(task="test")
        step = state.add_plan_step("Step 1")
        state.set_step_status(step.id, "completed", output="done")
        assert step.status == "completed"
        assert step.output == "done"

    def test_current_step(self):
        state = AgentState(task="test")
        step1 = state.add_plan_step("Step 1")
        step2 = state.add_plan_step("Step 2")
        state.current_step_id = step1.id
        assert state.current_step == step1

    def test_progress(self):
        state = AgentState(task="test")
        step1 = state.add_plan_step("Step 1")
        step2 = state.add_plan_step("Step 2")
        state.set_step_status(step1.id, "completed")
        assert state.progress == 0.5

    def test_complete(self):
        state = AgentState(task="test")
        state.complete()
        assert state.status == RunStatus.COMPLETED
        assert state.completed_at is not None

    def test_fail(self):
        state = AgentState(task="test")
        state.fail()
        assert state.status == RunStatus.FAILED

    def test_add_assumption(self):
        state = AgentState(task="test")
        state.add_assumption("file exists", True)
        assert state.assumptions["file exists"] is True

    def test_invalidate_assumption(self):
        state = AgentState(task="test")
        state.add_assumption("file exists", True)
        state.invalidate_assumption("file exists")
        assert state.assumptions["file exists"] is False

    def test_add_learned_fact(self):
        state = AgentState(task="test")
        state.add_learned_fact("Redis is required")
        assert "Redis is required" in state.learned_facts

    def test_add_duplicate_fact(self):
        state = AgentState(task="test")
        state.add_learned_fact("Redis is required")
        state.add_learned_fact("Redis is required")
        assert state.learned_facts.count("Redis is required") == 1

    def test_to_dict(self):
        state = AgentState(task="test")
        d = state.to_dict()
        assert d["task"] == "test"
        assert d["status"] == "pending"
        assert "run_id" in d

    def test_from_dict(self):
        state = AgentState(task="test")
        state.add_plan_step("Step 1")
        d = state.to_dict()
        restored = AgentState.from_dict(d)
        assert restored.task == "test"
        assert len(restored.plan) == 1

    def test_serialization_roundtrip(self):
        state = AgentState(task="test", project_id="/tmp/proj")
        state.add_plan_step("Step 1", "cap1")
        state.add_learned_fact("fact1")
        state.add_assumption("assumption1", True)

        d = state.to_dict()
        restored = AgentState.from_dict(d)

        assert restored.task == state.task
        assert restored.project_id == state.project_id
        assert len(restored.plan) == len(state.plan)
        assert len(restored.learned_facts) == len(state.learned_facts)
        assert restored.assumptions == state.assumptions

    def test_add_execution_record(self):
        state = AgentState(task="test")
        state.add_execution_record({"action": "read", "result": "ok"})
        assert len(state.execution_history) == 1
        assert state.execution_history[0]["action"] == "read"

    def test_add_verification_result(self):
        state = AgentState(task="test")
        state.add_verification_result({"name": "tests", "passed": True})
        assert len(state.verification_results) == 1

    def test_completed_steps(self):
        state = AgentState(task="test")
        step1 = state.add_plan_step("Step 1")
        step2 = state.add_plan_step("Step 2")
        state.set_step_status(step1.id, "completed")
        assert len(state.completed_steps) == 1

    def test_failed_steps(self):
        state = AgentState(task="test")
        step1 = state.add_plan_step("Step 1")
        state.set_step_status(step1.id, "failed")
        assert len(state.failed_steps) == 1


class TestStateStore:
    def test_save_state(self):
        mock_memory = MagicMock()
        mock_memory.store.return_value = {"id": "mem1"}
        store = StateStore(mock_memory, "/tmp/proj")

        state = AgentState(task="test")
        result = store.save_state(state)
        assert result is not None
        mock_memory.store.assert_called_once()

    def test_load_state(self):
        mock_memory = MagicMock()
        state = AgentState(task="test")
        import json
        content = f"ARGUS_STATE:{state.run_id}\n{json.dumps(state.to_dict(), default=str)}"
        mock_memory.search.return_value = [{"id": "mem1", "content": content}]
        store = StateStore(mock_memory, "/tmp/proj")

        loaded = store.load_state(state.run_id)
        assert loaded is not None
        assert loaded.task == "test"

    def test_load_state_not_found(self):
        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        store = StateStore(mock_memory, "/tmp/proj")
        loaded = store.load_state("nonexistent")
        assert loaded is None

    def test_save_no_memory(self):
        store = StateStore(None, "/tmp/proj")
        state = AgentState(task="test")
        result = store.save_state(state)
        assert result is None

    def test_load_no_memory(self):
        store = StateStore(None, "/tmp/proj")
        loaded = store.load_state("run1")
        assert loaded is None


class TestStateManager:
    def test_create_state(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test task", project_path="/tmp/proj")
        assert state.task == "test task"
        assert state.status == RunStatus.RUNNING
        assert state.run_id in manager._active_states

    def test_create_state_with_plan(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        plan = [
            {"description": "Step 1", "capability_id": "cap1"},
            {"description": "Step 2", "capability_id": "cap2"},
        ]
        state = manager.create_state("test", plan=plan)
        assert len(state.plan) == 2
        assert state.current_step_id == state.plan[0].id

    def test_get_state(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        retrieved = manager.get_state(state.run_id)
        assert retrieved is not None
        assert retrieved.run_id == state.run_id

    def test_set_phase(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.set_phase(state.run_id, "executing")
        assert state.current_phase == "executing"

    def test_set_step_status(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        step = state.add_plan_step("Step 1")
        manager.set_step_status(state.run_id, step.id, "completed", output="done")
        assert step.status == "completed"

    def test_advance_step(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        state.add_plan_step("Step 1")
        state.add_plan_step("Step 2")
        state.current_step_id = state.plan[0].id
        state.plan[0].status = "active"

        next_step = manager.advance_step(state.run_id)
        assert next_step is not None
        assert next_step.description == "Step 2"
        assert state.plan[0].status == "completed"

    def test_advance_step_completes_run(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        state.add_plan_step("Step 1")
        state.current_step_id = state.plan[0].id
        state.plan[0].status = "active"

        next_step = manager.advance_step(state.run_id)
        assert next_step is None
        assert state.status == RunStatus.COMPLETED

    def test_complete_run(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.complete_run(state.run_id)
        assert state.status == RunStatus.COMPLETED
        assert state.run_id not in manager._active_states

    def test_fail_run(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.fail_run(state.run_id)
        assert state.status == RunStatus.FAILED

    def test_pause_and_resume(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.pause_run(state.run_id)
        assert state.status == RunStatus.PAUSED

        resumed = manager.resume_run(state.run_id)
        assert resumed is not None
        assert resumed.status == RunStatus.RUNNING

    def test_add_learned_fact(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.add_learned_fact(state.run_id, "Redis is required")
        assert "Redis is required" in state.learned_facts

    def test_add_assumption(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.add_assumption(state.run_id, "file exists", True)
        assert state.assumptions["file exists"] is True

    def test_invalidate_assumption(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.add_assumption(state.run_id, "file exists", True)
        manager.invalidate_assumption(state.run_id, "file exists")
        assert state.assumptions["file exists"] is False

    def test_add_execution_record(self):
        mock_store = MagicMock()
        manager = StateManager(mock_store)
        state = manager.create_state("test")
        manager.add_execution_record(state.run_id, {"action": "read"})
        assert len(state.execution_history) == 1


class TestStateSnapshot:
    def test_capture(self):
        state = AgentState(task="test")
        snapshot = StateSnapshot.capture(state, "after_step_1")
        assert snapshot.run_id == state.run_id
        assert snapshot.label == "after_step_1"

    def test_to_dict(self):
        state = AgentState(task="test")
        snapshot = StateSnapshot.capture(state)
        d = snapshot.to_dict()
        assert d["run_id"] == state.run_id
        assert "state" in d

    def test_from_dict(self):
        state = AgentState(task="test")
        snapshot = StateSnapshot.capture(state, "label")
        d = snapshot.to_dict()
        restored = StateSnapshot.from_dict(d)
        assert restored.run_id == state.run_id
        assert restored.label == "label"


class TestSnapshotManager:
    def test_capture(self):
        mgr = SnapshotManager()
        state = AgentState(task="test")
        snapshot = mgr.capture(state, "label")
        assert snapshot.label == "label"

    def test_get_snapshots(self):
        mgr = SnapshotManager()
        state = AgentState(task="test")
        mgr.capture(state, "s1")
        mgr.capture(state, "s2")
        snapshots = mgr.get_snapshots(state.run_id)
        assert len(snapshots) == 2

    def test_get_last_snapshot(self):
        mgr = SnapshotManager()
        state = AgentState(task="test")
        mgr.capture(state, "s1")
        mgr.capture(state, "s2")
        last = mgr.get_last_snapshot(state.run_id)
        assert last.label == "s2"

    def test_max_snapshots(self):
        mgr = SnapshotManager(max_snapshots_per_run=3)
        state = AgentState(task="test")
        mgr.capture(state, "s1")
        mgr.capture(state, "s2")
        mgr.capture(state, "s3")
        mgr.capture(state, "s4")
        snapshots = mgr.get_snapshots(state.run_id)
        assert len(snapshots) == 3

    def test_clear(self):
        mgr = SnapshotManager()
        state = AgentState(task="test")
        mgr.capture(state)
        mgr.clear(state.run_id)
        assert len(mgr.get_snapshots(state.run_id)) == 0