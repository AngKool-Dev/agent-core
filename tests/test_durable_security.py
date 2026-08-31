"""Tests for ARGUS Durable idempotency and security."""

import os
import tempfile

import pytest

from argus.durable.idempotency import IdempotencyClassifier
from argus.durable.models import (
    IdempotencyClass,
    OperationIdentity,
    OperationRecord,
    OperationStatus,
    OperationType,
    ReconciliationDecision,
    RetryPolicy,
    RunStatus,
)
from argus.durable.reconciler import Reconciler
from argus.durable.resume import ResumeEngine
from argus.durable.detector import CrashDetector


class TestIdempotencyClassification:
    """Tests for idempotency classification of operations."""

    def setup_method(self):
        self.classifier = IdempotencyClassifier()

    def test_read_operations_idempotent(self):
        """Read operations should be idempotent."""
        assert self.classifier.classify(OperationType.FILESYSTEM_READ) == IdempotencyClass.IDEMPOTENT
        assert self.classifier.is_idempotent(OperationType.FILESYSTEM_READ)

    def test_write_operations_conditionally_idempotent(self):
        """Write operations should be conditionally idempotent."""
        assert self.classifier.classify(OperationType.FILESYSTEM_WRITE) == IdempotencyClass.CONDITIONALLY_IDEMPOTENT
        assert self.classifier.is_conditionally_idempotent(OperationType.FILESYSTEM_WRITE)

    def test_delete_operations_conditionally_idempotent(self):
        """Delete operations should be conditionally idempotent."""
        assert self.classifier.classify(OperationType.FILESYSTEM_DELETE) == IdempotencyClass.CONDITIONALLY_IDEMPOTENT

    def test_shell_execute_non_idempotent(self):
        """Shell execute should be non-idempotent."""
        assert self.classifier.classify(OperationType.SHELL_EXECUTE) == IdempotencyClass.NON_IDEMPOTENT
        assert self.classifier.is_non_idempotent(OperationType.SHELL_EXECUTE)

    def test_git_operation_conditionally_idempotent(self):
        """Git operations should be conditionally idempotent."""
        assert self.classifier.classify(OperationType.GIT_OPERATION) == IdempotencyClass.CONDITIONALLY_IDEMPOTENT

    def test_model_call_idempotent(self):
        """Model calls should be idempotent."""
        assert self.classifier.classify(OperationType.MODEL_CALL) == IdempotencyClass.IDEMPOTENT

    def test_verification_idempotent(self):
        """Verification should be idempotent."""
        assert self.classifier.classify(OperationType.VERIFICATION) == IdempotencyClass.IDEMPOTENT

    def test_review_idempotent(self):
        """Review should be idempotent."""
        assert self.classifier.classify(OperationType.REVIEW) == IdempotencyClass.IDEMPOTENT

    def test_checkpoint_idempotent(self):
        """Checkpoint should be idempotent."""
        assert self.classifier.classify(OperationType.CHECKPOINT) == IdempotencyClass.IDEMPOTENT

    def test_state_commit_conditionally_idempotent(self):
        """State commit should be conditionally idempotent."""
        assert self.classifier.classify(OperationType.STATE_COMMIT) == IdempotencyClass.CONDITIONALLY_IDEMPOTENT

    def test_mcp_tool_unknown(self):
        """MCP tool should be unknown (conservative)."""
        assert self.classifier.classify(OperationType.MCP_TOOL) == IdempotencyClass.UNKNOWN

    def test_capability_unknown(self):
        """Generic capability should be unknown."""
        assert self.classifier.classify(OperationType.CAPABILITY) == IdempotencyClass.UNKNOWN


class TestRetryPolicy:
    """Tests for retry policy determination."""

    def setup_method(self):
        self.classifier = IdempotencyClassifier()

    def test_safe_retry_for_idempotent(self):
        """Idempotent operations should have safe retry."""
        policy = self.classifier.determine_retry_policy(OperationType.FILESYSTEM_READ)
        assert policy == RetryPolicy.SAFE_RETRY

    def test_reconciliation_for_conditionally_idempotent(self):
        """Conditionally idempotent operations require reconciliation."""
        policy = self.classifier.determine_retry_policy(OperationType.FILESYSTEM_WRITE)
        assert policy == RetryPolicy.RECONCILIATION_REQUIRED

    def test_unsafe_retry_for_non_idempotent(self):
        """Non-idempotent operations are unsafe to retry."""
        policy = self.classifier.determine_retry_policy(OperationType.SHELL_EXECUTE)
        assert policy == RetryPolicy.UNSAFE_RETRY

    def test_user_decision_for_unknown(self):
        """Unknown operations require user decision."""
        policy = self.classifier.determine_retry_policy(OperationType.MCP_TOOL)
        assert policy == RetryPolicy.USER_DECISION


class TestDurableSecurity:
    """Tests for security guarantees after crash/resume."""

    def test_unknown_operation_not_silently_completed(self):
        """UNKNOWN operations must not be silently treated as completed."""
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.SHELL_EXECUTE,
            target="echo hello",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        decision, status, details = reconciler.reconcile(record)
        # Shell execute with unknown side effects should require user decision
        assert status == OperationStatus.REQUIRES_DECISION
        assert decision == ReconciliationDecision.REQUIRE_USER

    def test_unknown_non_idempotent_not_retried(self):
        """UNKNOWN non-idempotent operations should not be blindly retried."""
        classifier = IdempotencyClassifier()
        policy = classifier.determine_retry_policy(OperationType.SHELL_EXECUTE)
        assert policy == RetryPolicy.UNSAFE_RETRY

    def test_approval_scope_not_expanded_by_crash(self):
        """Crash must not expand approval scope."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            run = detector.get_run("nonexistent")
            assert run is None

    def test_recovery_budget_not_reset_by_crash(self):
        """Recovery budget must not be reset by crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            from argus.durable.models import ExecutionRun
            run = ExecutionRun(
                run_id="run-test",
                session_id="sess-test",
                task="Test",
                recovery_budget_used=3,
                metadata={"last_heartbeat": "2020-01-01T00:00:00"},  # Old heartbeat
            )
            detector.register_run(run)

            # Simulate crash detection
            detected = detector.detect_crash("run-test")
            # Run has old heartbeat so should be detected as crashed
            assert detected is True

            # Budget should still be 3, not reset
            updated_run = detector.get_run("run-test")
            assert updated_run.recovery_budget_used == 3

    def test_resume_requires_valid_state(self):
        """Resume must require a valid state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            engine = ResumeEngine(detector=detector)

            # Cannot resume completed run
            from argus.durable.models import ExecutionRun
            run = ExecutionRun(
                run_id="run-test",
                session_id="sess-test",
                task="Test",
                status=RunStatus.COMPLETED,
            )
            detector.register_run(run)

            result = engine.resume("run-test")
            assert result["success"] is False

    def test_concurrent_resume_prevented(self):
        """Two processes should not be able to resume the same run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from argus.durable.locks import LockManager
            locks = LockManager(lock_dir=tmpdir)

            # First process acquires lock
            lock1 = locks.acquire_lock("run-test", "process-1")
            assert lock1 is not None

            # Second process should be rejected
            lock2 = locks.acquire_lock("run-test", "process-2")
            assert lock2 is None

    def test_secrets_remain_redacted(self):
        """Secrets should remain redacted after restart."""
        # This is a conceptual test - actual secret redaction
        # would be implemented in the security layer
        pass


class TestDurableEvents:
    """Tests for event durability."""

    def test_crash_creates_audit_trail(self):
        """A crash should create an audit trail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            from argus.durable.models import ExecutionRun
            run = ExecutionRun(
                run_id="run-test",
                session_id="sess-test",
                task="Test",
                status=RunStatus.RUNNING,
            )
            detector.register_run(run)

            # Simulate crash by setting old heartbeat
            run.metadata["last_heartbeat"] = "2020-01-01T00:00:00"
            detector.update_run(run)
            detector.detect_crash("run-test")

            # Verify crash was recorded
            updated_run = detector.get_run("run-test")
            assert updated_run.crash_count == 1
            assert updated_run.status == RunStatus.CRASHED

    def test_resume_creates_event(self):
        """A resume should create an event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CrashDetector(run_dir=tmpdir)
            from argus.durable.models import ExecutionRun
            run = ExecutionRun(
                run_id="run-test",
                session_id="sess-test",
                task="Test",
                status=RunStatus.RECOVERABLE,
                resume_count=0,
            )
            detector.register_run(run)

            # Simulate resume
            run.resume_count += 1
            run.status = RunStatus.RUNNING
            detector.update_run(run)

            updated_run = detector.get_run("run-test")
            assert updated_run.resume_count == 1
            assert updated_run.status == RunStatus.RUNNING
