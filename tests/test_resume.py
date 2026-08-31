"""Tests for ARGUS Durable resume functionality."""

import os
import tempfile

import pytest

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.lifecycle import LifecycleManager
from argus.durable.locks import LockManager
from argus.durable.models import (
    ExecutionRun,
    OperationIdentity,
    OperationRecord,
    OperationStatus,
    OperationType,
    RunStatus,
)
from argus.durable.resume import ResumeEngine


@pytest.fixture
def dirs():
    """Create separate directories for runs and journals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = os.path.join(tmpdir, "runs")
        journal_dir = os.path.join(tmpdir, "journals")
        os.makedirs(run_dir)
        os.makedirs(journal_dir)
        yield run_dir, journal_dir


class TestResumeEngine:
    """Tests for ResumeEngine."""

    def test_analyze_run_not_found(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        engine = ResumeEngine(detector=detector)
        result = engine.analyze_run("nonexistent")
        assert "error" in result

    def test_analyze_run_found(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.CRASHED,
        )
        detector.register_run(run)

        engine = ResumeEngine(detector=detector)
        result = engine.analyze_run("run-test")
        assert result["run_id"] == "run-test"
        assert result["can_resume"] is True

    def test_dry_run_resume(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.CRASHED,
        )
        detector.register_run(run)

        # Add an UNKNOWN operation
        journal.create_journal("run-test")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-test",
            session_id="sess-test",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_READ,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        journal._journals["run-test"].add_operation(record)
        journal._save_journal(journal._journals["run-test"])

        engine = ResumeEngine(detector=detector, journal=journal)
        result = engine.dry_run_resume("run-test")

        assert result["can_resume"] is True
        assert result["unknown_operations"] == 1
        assert len(result["reconciliation_plans"]) == 1

    def test_resume_not_found(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        engine = ResumeEngine(detector=detector)
        result = engine.resume("nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_resume_invalid_state(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.COMPLETED,
        )
        detector.register_run(run)

        engine = ResumeEngine(detector=detector)
        result = engine.resume("run-test")
        assert result["success"] is False
        assert "not in a resumable state" in result["error"]

    def test_resume_success(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.CRASHED,
        )
        detector.register_run(run)

        # Add an UNKNOWN idempotent operation
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-test",
            session_id="sess-test",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_READ,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        journal.create_journal("run-test")
        journal._journals["run-test"].add_operation(record)
        journal._save_journal(journal._journals["run-test"])

        engine = ResumeEngine(detector=detector, journal=journal)
        result = engine.resume("run-test")

        assert result["success"] is True
        assert result["dry_run"] is False
        assert len(result["reconciliation_results"]) == 1

    def test_resume_dry_run(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.CRASHED,
        )
        detector.register_run(run)

        engine = ResumeEngine(detector=detector, journal=journal)
        result = engine.resume("run-test", mode="dry_run")

        assert result["success"] is True
        assert result["dry_run"] is True

    def test_mark_run_completed(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.RUNNING,
        )
        detector.register_run(run)

        engine = ResumeEngine(detector=detector)
        result = engine.mark_run_completed("run-test")

        assert result is not None
        assert result.status == RunStatus.COMPLETED
        assert result.completed_at is not None

    def test_mark_run_failed(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.RUNNING,
        )
        detector.register_run(run)

        engine = ResumeEngine(detector=detector)
        result = engine.mark_run_failed("run-test")

        assert result is not None
        assert result.status == RunStatus.FAILED

    def test_mark_run_abandoned(self, dirs):
        run_dir, _ = dirs
        detector = CrashDetector(run_dir=run_dir)
        run = ExecutionRun(
            run_id="run-test",
            session_id="sess-test",
            task="Test task",
            status=RunStatus.CRASHED,
        )
        detector.register_run(run)

        engine = ResumeEngine(detector=detector)
        result = engine.mark_run_abandoned("run-test")

        assert result is not None
        assert result.status == RunStatus.ABANDONED


class TestLifecycleManager:
    """Tests for LifecycleManager."""

    def test_create_run(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)
        manager = LifecycleManager(detector=detector, journal=journal)

        run = manager.create_run(
            session_id="sess-test",
            task="Test task",
        )
        assert run.run_id is not None
        assert run.status == RunStatus.RUNNING
        assert run.session_id == "sess-test"

    def test_valid_transition(self):
        manager = LifecycleManager()
        assert manager.is_valid_transition(RunStatus.RUNNING, RunStatus.CRASHED)
        assert manager.is_valid_transition(RunStatus.CRASHED, RunStatus.RECOVERABLE)
        assert manager.is_valid_transition(RunStatus.RECOVERABLE, RunStatus.RECONCILING)
        assert not manager.is_valid_transition(RunStatus.COMPLETED, RunStatus.RUNNING)

    def test_invalid_transition_raises(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)
        manager = LifecycleManager(detector=detector, journal=journal)

        run = manager.create_run(session_id="sess-1", task="Test")
        with pytest.raises(ValueError):
            manager.transition(run.run_id, RunStatus.RECONCILING)

    def test_can_resume(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)
        manager = LifecycleManager(detector=detector, journal=journal)

        run = manager.create_run(session_id="sess-1", task="Test")
        assert not manager.can_resume(run.run_id)

        manager.transition(run.run_id, RunStatus.CRASHED)
        assert manager.can_resume(run.run_id)

    def test_is_terminal(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)
        manager = LifecycleManager(detector=detector, journal=journal)

        run = manager.create_run(session_id="sess-1", task="Test")
        assert not manager.is_terminal(run.run_id)

        manager.transition(run.run_id, RunStatus.CRASHED)
        manager.transition(run.run_id, RunStatus.RECOVERABLE)
        manager.transition(run.run_id, RunStatus.RECONCILING)
        manager.transition(run.run_id, RunStatus.RESUMING)
        manager.transition(run.run_id, RunStatus.RUNNING)
        manager.transition(run.run_id, RunStatus.COMPLETED)
        assert manager.is_terminal(run.run_id)

    def test_get_runs_by_status(self, dirs):
        run_dir, journal_dir = dirs
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)
        manager = LifecycleManager(detector=detector, journal=journal)

        run1 = manager.create_run(session_id="sess-1", task="Task 1")
        run2 = manager.create_run(session_id="sess-2", task="Task 2")

        # Verify runs were created
        all_runs = manager.get_all_runs()
        assert len(all_runs) == 2

        running = manager.get_runs_by_status(RunStatus.RUNNING)
        assert len(running) == 2

        manager.transition(run1.run_id, RunStatus.CRASHED)
        running = manager.get_runs_by_status(RunStatus.RUNNING)
        assert len(running) == 1
        crashed = manager.get_runs_by_status(RunStatus.CRASHED)
        assert len(crashed) == 1


class TestLockManager:
    """Tests for LockManager."""

    def test_acquire_lock(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        lock = locks.acquire_lock("run-test", "process-1")
        assert lock is not None
        assert lock.run_id == "run-test"
        assert lock.owner_id == "process-1"

    def test_acquire_lock_already_held(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        locks.acquire_lock("run-test", "process-1")
        lock = locks.acquire_lock("run-test", "process-2")
        assert lock is None

    def test_release_lock(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        locks.acquire_lock("run-test", "process-1")
        result = locks.release_lock("run-test", "process-1")
        assert result is True
        assert not locks.is_locked("run-test")

    def test_release_lock_wrong_owner(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        locks.acquire_lock("run-test", "process-1")
        result = locks.release_lock("run-test", "process-2")
        assert result is False
        assert locks.is_locked("run-test")

    def test_is_locked(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        assert not locks.is_locked("run-test")
        locks.acquire_lock("run-test", "process-1")
        assert locks.is_locked("run-test")

    def test_get_owner(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        locks.acquire_lock("run-test", "process-1")
        assert locks.get_owner("run-test") == "process-1"

    def test_force_unlock(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir)
        locks.acquire_lock("run-test", "process-1")
        locks.force_unlock("run-test")
        assert not locks.is_locked("run-test")

    def test_stale_lock_cleanup(self, dirs):
        _, tmpdir = dirs
        lock_dir = os.path.join(tmpdir, "locks")
        locks = LockManager(lock_dir=lock_dir, lock_timeout=0)
        locks.acquire_lock("run-test", "process-1")
        # Lock should be immediately stale
        import time
        time.sleep(0.1)
        cleaned = locks.cleanup_stale_locks()
        assert cleaned == 1
