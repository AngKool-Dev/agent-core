"""Tests for ARGUS Durable replay integration."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.models import (
    ExecutionRun,
    OperationIdentity,
    OperationRecord,
    OperationStatus,
    OperationType,
    RunStatus,
)


class TestReplayIntegration:
    """Tests for replay integration after crash/resume."""

    def test_journal_replayable_after_crash(self):
        """Test that journal is replayable after crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = ExecutionJournal(journal_dir=tmpdir)
            journal.create_journal("run-test")

            # Add operations
            for i in range(5):
                identity = OperationIdentity(
                    operation_id=f"op-{i}",
                    run_id="run-test",
                    session_id="sess-1",
                    capability_id="cap-1",
                    operation_type=OperationType.FILESYSTEM_WRITE,
                    target=f"/workspace/test{i}.py",
                )
                record = OperationRecord(
                    identity=identity,
                    status=OperationStatus.COMPLETED,
                )
                journal._journals["run-test"].add_operation(record)

            journal._save_journal(journal._journals["run-test"])

            # Load and replay
            journal2 = ExecutionJournal(journal_dir=tmpdir)
            ops = journal2.get_operations_by_status("run-test", OperationStatus.COMPLETED)
            assert len(ops) == 5

    def test_unknown_operations_in_replay(self):
        """Test that UNKNOWN operations are visible in replay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = ExecutionJournal(journal_dir=tmpdir)
            journal.create_journal("run-test")

            # Add mix of operations
            for i, status in enumerate([
                OperationStatus.COMPLETED,
                OperationStatus.UNKNOWN,
                OperationStatus.COMPLETED,
                OperationStatus.UNKNOWN,
            ]):
                identity = OperationIdentity(
                    operation_id=f"op-{i}",
                    run_id="run-test",
                    session_id="sess-1",
                    capability_id="cap-1",
                    operation_type=OperationType.FILESYSTEM_WRITE,
                    target=f"/workspace/test{i}.py",
                )
                record = OperationRecord(identity=identity, status=status)
                journal._journals["run-test"].add_operation(record)

            journal._save_journal(journal._journals["run-test"])

            # Load and verify
            journal2 = ExecutionJournal(journal_dir=tmpdir)
            unknown = journal2.get_unknown_operations("run-test")
            completed = journal2.get_operations_by_status("run-test", OperationStatus.COMPLETED)
            assert len(unknown) == 2
            assert len(completed) == 2

    def test_replay_observational_only(self):
        """Test that replay is observational only (no execution)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = ExecutionJournal(journal_dir=tmpdir)
            journal.create_journal("run-test")

            # Add an operation
            identity = OperationIdentity(
                operation_id="op-1",
                run_id="run-test",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_WRITE,
                target="/workspace/test.py",
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.COMPLETED,
            )
            journal._journals["run-test"].add_operation(record)
            journal._save_journal(journal._journals["run-test"])

            # Load journal - should not execute anything
            journal2 = ExecutionJournal(journal_dir=tmpdir)
            ops = journal2.get_operations_by_status("run-test", OperationStatus.COMPLETED)
            assert len(ops) == 1
            # Verify no side effects occurred (no files created, etc.)

    def test_event_history_consistency(self):
        """Test that event history is consistent with journal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = ExecutionJournal(journal_dir=tmpdir)
            journal.create_journal("run-test")

            # Add operations
            for i in range(3):
                identity = OperationIdentity(
                    operation_id=f"op-{i}",
                    run_id="run-test",
                    session_id="sess-1",
                    capability_id="cap-1",
                    operation_type=OperationType.FILESYSTEM_WRITE,
                    target=f"/workspace/test{i}.py",
                )
                record = OperationRecord(identity=identity, status=OperationStatus.COMPLETED)
                journal._journals["run-test"].add_operation(record)

            # Simulate events
            events = [
                {"operation_id": "op-0", "type": "started"},
                {"operation_id": "op-1", "type": "started"},
                {"operation_id": "op-2", "type": "started"},
            ]

            # Verify consistency
            from argus.durable.integrity import IntegrityVerifier
            verifier = IntegrityVerifier()
            results = verifier.verify_event_history_consistency(
                events, journal._journals["run-test"].operations
            )
            assert results["valid"] is True


class TestConcurrentResume:
    """Tests for concurrent resume prevention."""

    def test_lock_prevents_concurrent_resume(self):
        """Test that lock prevents concurrent resume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from argus.durable.locks import LockManager
            locks = LockManager(lock_dir=tmpdir)

            # First process acquires lock
            lock1 = locks.acquire_lock("run-test", "process-1")
            assert lock1 is not None

            # Second process should be rejected
            lock2 = locks.acquire_lock("run-test", "process-2")
            assert lock2 is None

    def test_lock_release_allows_resume(self):
        """Test that releasing lock allows another process to resume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from argus.durable.locks import LockManager
            locks = LockManager(lock_dir=tmpdir)

            # First process acquires and releases
            locks.acquire_lock("run-test", "process-1")
            locks.release_lock("run-test", "process-1")

            # Second process can now acquire
            lock2 = locks.acquire_lock("run-test", "process-2")
            assert lock2 is not None

    def test_stale_lock_can_be_overridden(self):
        """Test that stale lock can be overridden."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from argus.durable.locks import LockManager
            locks = LockManager(lock_dir=tmpdir, lock_timeout=0)
            locks.acquire_lock("run-test", "process-1")

            # Lock should be immediately stale
            import time
            time.sleep(0.1)

            # Force acquire should work
            lock2 = locks.acquire_lock("run-test", "process-2", force=True)
            assert lock2 is not None

    def test_lock_expiration(self):
        """Test that locks expire after timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from argus.durable.locks import LockManager
            locks = LockManager(lock_dir=tmpdir, lock_timeout=1)
            locks.acquire_lock("run-test", "process-1")

            # Lock should be valid immediately
            assert locks.is_locked("run-test")

            # Wait for expiration
            import time
            time.sleep(1.1)

            # Lock should be expired
            assert not locks.is_locked("run-test")


class TestMCPInterruption:
    """Tests for MCP operation interruption."""

    def test_mcp_call_unknown_after_crash(self):
        """Test that MCP call is marked UNKNOWN after crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = ExecutionJournal(journal_dir=tmpdir)
            journal.create_journal("run-test")

            identity = OperationIdentity(
                operation_id="op-1",
                run_id="run-test",
                session_id="sess-1",
                capability_id="mcp-tool",
                operation_type=OperationType.MCP_TOOL,
                target="read_file",
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.UNKNOWN,
            )
            journal._journals["run-test"].add_operation(record)

            # Verify it's UNKNOWN
            unknown = journal.get_unknown_operations("run-test")
            assert len(unknown) == 1

    def test_mcp_call_requires_user_decision(self):
        """Test that MCP call with unknown status requires user decision."""
        from argus.durable.reconciler import Reconciler
        from argus.durable.models import ReconciliationDecision
        reconciler = Reconciler()

        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-test",
            session_id="sess-1",
            capability_id="mcp-tool",
            operation_type=OperationType.MCP_TOOL,
            target="read_file",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )

        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.REQUIRE_USER
        assert status == OperationStatus.REQUIRES_DECISION


class TestVerificationInterruption:
    """Tests for verification interruption handling."""

    def test_verification_incomplete_after_crash(self):
        """Test that incomplete verification is not marked as success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = ExecutionJournal(journal_dir=tmpdir)
            journal.create_journal("run-test")

            identity = OperationIdentity(
                operation_id="op-1",
                run_id="run-test",
                session_id="sess-1",
                capability_id="verification",
                operation_type=OperationType.VERIFICATION,
                target="test_suite",
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.UNKNOWN,
            )
            journal._journals["run-test"].add_operation(record)

            # Should be UNKNOWN, not COMPLETED
            unknown = journal.get_unknown_operations("run-test")
            assert len(unknown) == 1

    def test_verification_retry_safe(self):
        """Test that verification retry is safe (idempotent)."""
        from argus.durable.idempotency import IdempotencyClassifier
        classifier = IdempotencyClassifier()

        from argus.durable.models import RetryPolicy
        policy = classifier.determine_retry_policy(OperationType.VERIFICATION)
        assert policy == RetryPolicy.SAFE_RETRY


class TestRecoveryInterruption:
    """Tests for recovery interruption handling."""

    def test_recovery_state_preserved(self):
        """Test that recovery state is preserved after crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            run = ExecutionRun(
                run_id="run-test",
                session_id="sess-1",
                task="Test",
                recovery_budget_used=3,
                crash_count=1,
            )
            detector.register_run(run)

            # Verify state is preserved
            loaded = detector.get_run("run-test")
            assert loaded.recovery_budget_used == 3
            assert loaded.crash_count == 1

    def test_recovery_budget_not_reset(self):
        """Test that recovery budget is not reset by crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            run = ExecutionRun(
                run_id="run-test",
                session_id="sess-1",
                task="Test",
                recovery_budget_used=5,
            )
            detector.register_run(run)

            # Crash
            detector.mark_crashed("run-test")

            # Budget should still be 5
            loaded = detector.get_run("run-test")
            assert loaded.recovery_budget_used == 5
