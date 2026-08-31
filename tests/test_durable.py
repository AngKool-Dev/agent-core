"""Tests for ARGUS Durable Execution models."""

import pytest

from argus.durable.models import (
    Checkpoint,
    CheckpointPhase,
    CrashPoint,
    ExecutionRun,
    IdempotencyClass,
    LockState,
    OperationIdentity,
    OperationJournal,
    OperationRecord,
    OperationStatus,
    OperationType,
    ReconciliationDecision,
    ResumeMode,
    RetryPolicy,
    RunStatus,
    generate_checkpoint_id,
    generate_operation_id,
    generate_run_id,
)


class TestOperationStatus:
    """Tests for OperationStatus enum."""

    def test_status_values(self):
        assert OperationStatus.INTENT.value == "intent"
        assert OperationStatus.STARTED.value == "started"
        assert OperationStatus.PROGRESS.value == "progress"
        assert OperationStatus.COMPLETED.value == "completed"
        assert OperationStatus.FAILED.value == "failed"
        assert OperationStatus.UNKNOWN.value == "unknown"
        assert OperationStatus.RECONCILED_COMPLETED.value == "reconciled_completed"
        assert OperationStatus.RECONCILED_NOT_EXECUTED.value == "reconciled_not_executed"
        assert OperationStatus.REQUIRES_DECISION.value == "requires_decision"


class TestOperationType:
    """Tests for OperationType enum."""

    def test_type_values(self):
        assert OperationType.FILESYSTEM_READ.value == "filesystem.read"
        assert OperationType.FILESYSTEM_WRITE.value == "filesystem.write"
        assert OperationType.FILESYSTEM_DELETE.value == "filesystem.delete"
        assert OperationType.SHELL_EXECUTE.value == "shell.execute"
        assert OperationType.GIT_OPERATION.value == "git.operation"
        assert OperationType.MCP_TOOL.value == "mcp.tool"
        assert OperationType.MODEL_CALL.value == "model.call"
        assert OperationType.VERIFICATION.value == "verification"
        assert OperationType.RECOVERY.value == "recovery"
        assert OperationType.REVIEW.value == "review"


class TestRunStatus:
    """Tests for RunStatus enum."""

    def test_status_values(self):
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.PAUSED.value == "paused"
        assert RunStatus.CRASHED.value == "crashed"
        assert RunStatus.RECOVERABLE.value == "recoverable"
        assert RunStatus.RECONCILING.value == "reconciling"
        assert RunStatus.RESUMING.value == "resuming"
        assert RunStatus.COMPLETED.value == "completed"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.ABANDONED.value == "abandoned"


class TestCrashPoint:
    """Tests for CrashPoint enum."""

    def test_crash_points(self):
        assert CrashPoint.BEFORE_INTENT.value == "before_intent"
        assert CrashPoint.AFTER_START.value == "after_start"
        assert CrashPoint.DURING_OPERATION.value == "during_operation"
        assert CrashPoint.AFTER_COMPLETION.value == "after_completion"
        assert CrashPoint.BEFORE_STATE_COMMIT.value == "before_state_commit"
        assert CrashPoint.BEFORE_CHECKPOINT.value == "before_checkpoint"
        assert CrashPoint.BEFORE_VERIFICATION.value == "before_verification"
        assert CrashPoint.BEFORE_RECOVERY.value == "before_recovery"
        assert CrashPoint.BEFORE_REVIEW.value == "before_review"


class TestCheckpointPhase:
    """Tests for CheckpointPhase enum."""

    def test_phases(self):
        assert CheckpointPhase.BEFORE_PLAN.value == "before_plan"
        assert CheckpointPhase.AFTER_PLAN.value == "after_plan"
        assert CheckpointPhase.BEFORE_EXECUTION.value == "before_execution"
        assert CheckpointPhase.AFTER_EXECUTION.value == "after_execution"
        assert CheckpointPhase.BEFORE_VERIFICATION.value == "before_verification"
        assert CheckpointPhase.AFTER_VERIFICATION.value == "after_verification"


class TestIdempotencyClass:
    """Tests for IdempotencyClass enum."""

    def test_classes(self):
        assert IdempotencyClass.IDEMPOTENT.value == "idempotent"
        assert IdempotencyClass.CONDITIONALLY_IDEMPOTENT.value == "conditionally_idempotent"
        assert IdempotencyClass.NON_IDEMPOTENT.value == "non_idempotent"
        assert IdempotencyClass.UNKNOWN.value == "unknown"


class TestRetryPolicy:
    """Tests for RetryPolicy enum."""

    def test_policies(self):
        assert RetryPolicy.SAFE_RETRY.value == "safe_retry"
        assert RetryPolicy.UNSAFE_RETRY.value == "unsafe_retry"
        assert RetryPolicy.RECONCILIATION_REQUIRED.value == "reconciliation_required"
        assert RetryPolicy.APPROVAL_REQUIRED.value == "approval_required"
        assert RetryPolicy.USER_DECISION.value == "user_decision"


class TestReconciliationDecision:
    """Tests for ReconciliationDecision enum."""

    def test_decisions(self):
        assert ReconciliationDecision.RETRY.value == "retry"
        assert ReconciliationDecision.SKIP.value == "skip"
        assert ReconciliationDecision.MARK_COMPLETED.value == "mark_completed"
        assert ReconciliationDecision.MARK_FAILED.value == "mark_failed"
        assert ReconciliationDecision.REQUIRE_USER.value == "require_user"


class TestResumeMode:
    """Tests for ResumeMode enum."""

    def test_modes(self):
        assert ResumeMode.NORMAL.value == "normal"
        assert ResumeMode.DRY_RUN.value == "dry_run"
        assert ResumeMode.RECONCILE.value == "reconcile"


class TestOperationIdentity:
    """Tests for OperationIdentity model."""

    def test_create_identity(self):
        identity = OperationIdentity(
            operation_id="op-123",
            run_id="run-456",
            session_id="sess-789",
            capability_id="cap-abc",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
            normalized_arguments={"content": "hello"},
            attempt=1,
        )
        assert identity.operation_id == "op-123"
        assert identity.run_id == "run-456"
        assert identity.attempt == 1

    def test_fingerprint(self):
        identity = OperationIdentity(
            operation_id="op-123",
            run_id="run-456",
            session_id="sess-789",
            capability_id="cap-abc",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
            normalized_arguments={"content": "hello"},
        )
        fp1 = identity.fingerprint()
        fp2 = identity.fingerprint()
        assert fp1 == fp2  # Deterministic

    def test_fingerprint_different_args(self):
        identity1 = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
            normalized_arguments={"content": "hello"},
        )
        identity2 = OperationIdentity(
            operation_id="op-2",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
            normalized_arguments={"content": "world"},
        )
        assert identity1.fingerprint() != identity2.fingerprint()

    def test_to_dict(self):
        identity = OperationIdentity(
            operation_id="op-123",
            run_id="run-456",
            session_id="sess-789",
            capability_id="cap-abc",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        d = identity.to_dict()
        assert d["operation_id"] == "op-123"
        assert d["operation_type"] == "filesystem.write"

    def test_from_dict(self):
        d = {
            "operation_id": "op-123",
            "run_id": "run-456",
            "session_id": "sess-789",
            "capability_id": "cap-abc",
            "operation_type": "filesystem.write",
            "target": "/workspace/test.py",
            "normalized_arguments": {"content": "hello"},
            "attempt": 2,
        }
        identity = OperationIdentity.from_dict(d)
        assert identity.operation_id == "op-123"
        assert identity.attempt == 2


class TestOperationRecord:
    """Tests for OperationRecord model."""

    def test_create_record(self):
        identity = OperationIdentity(
            operation_id="op-123",
            run_id="run-456",
            session_id="sess-789",
            capability_id="cap-abc",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.STARTED,
        )
        assert record.status == OperationStatus.STARTED
        assert record.error is None

    def test_to_dict(self):
        identity = OperationIdentity(
            operation_id="op-123",
            run_id="run-456",
            session_id="sess-789",
            capability_id="cap-abc",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.COMPLETED,
            evidence={"result": "success"},
        )
        d = record.to_dict()
        assert d["status"] == "completed"
        assert d["evidence"]["result"] == "success"

    def test_from_dict(self):
        identity = OperationIdentity(
            operation_id="op-123",
            run_id="run-456",
            session_id="sess-789",
            capability_id="cap-abc",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.FAILED,
            error="File not found",
        )
        d = record.to_dict()
        restored = OperationRecord.from_dict(d)
        assert restored.status == OperationStatus.FAILED
        assert restored.error == "File not found"


class TestOperationJournal:
    """Tests for OperationJournal model."""

    def test_create_journal(self):
        journal = OperationJournal(run_id="run-123")
        assert journal.run_id == "run-123"
        assert len(journal.operations) == 0

    def test_add_operation(self):
        journal = OperationJournal(run_id="run-123")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-123",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(identity=identity, status=OperationStatus.STARTED)
        journal.add_operation(record)
        assert len(journal.operations) == 1

    def test_get_operation(self):
        journal = OperationJournal(run_id="run-123")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-123",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(identity=identity, status=OperationStatus.STARTED)
        journal.add_operation(record)
        found = journal.get_operation("op-1")
        assert found is not None
        assert found.identity.operation_id == "op-1"

    def test_get_operations_by_status(self):
        journal = OperationJournal(run_id="run-123")
        for i in range(3):
            identity = OperationIdentity(
                operation_id=f"op-{i}",
                run_id="run-123",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_WRITE,
                target=f"/workspace/test{i}.py",
            )
            status = OperationStatus.COMPLETED if i == 0 else OperationStatus.STARTED
            record = OperationRecord(identity=identity, status=status)
            journal.add_operation(record)

        completed = journal.get_operations_by_status(OperationStatus.COMPLETED)
        assert len(completed) == 1
        started = journal.get_operations_by_status(OperationStatus.STARTED)
        assert len(started) == 2

    def test_get_unknown_operations(self):
        journal = OperationJournal(run_id="run-123")
        for i in range(3):
            identity = OperationIdentity(
                operation_id=f"op-{i}",
                run_id="run-123",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_WRITE,
                target=f"/workspace/test{i}.py",
            )
            status = OperationStatus.UNKNOWN if i == 0 else OperationStatus.COMPLETED
            record = OperationRecord(identity=identity, status=status)
            journal.add_operation(record)

        unknown = journal.get_unknown_operations()
        assert len(unknown) == 1

    def test_to_dict(self):
        journal = OperationJournal(run_id="run-123")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-123",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(identity=identity, status=OperationStatus.STARTED)
        journal.add_operation(record)

        d = journal.to_dict()
        assert d["run_id"] == "run-123"
        assert len(d["operations"]) == 1

    def test_from_dict(self):
        journal = OperationJournal(run_id="run-123")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-123",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(identity=identity, status=OperationStatus.STARTED)
        journal.add_operation(record)

        d = journal.to_dict()
        restored = OperationJournal.from_dict(d)
        assert restored.run_id == "run-123"
        assert len(restored.operations) == 1


class TestCheckpoint:
    """Tests for Checkpoint model."""

    def test_create_checkpoint(self):
        checkpoint = Checkpoint(
            checkpoint_id="chk-123",
            run_id="run-456",
            phase=CheckpointPhase.BEFORE_EXECUTION,
            state_snapshot={"step": 1},
        )
        assert checkpoint.checkpoint_id == "chk-123"
        assert checkpoint.phase == CheckpointPhase.BEFORE_EXECUTION

    def test_to_dict(self):
        checkpoint = Checkpoint(
            checkpoint_id="chk-123",
            run_id="run-456",
            phase=CheckpointPhase.AFTER_EXECUTION,
            state_snapshot={"step": 2},
            operation_id="op-1",
        )
        d = checkpoint.to_dict()
        assert d["checkpoint_id"] == "chk-123"
        assert d["phase"] == "after_execution"
        assert d["operation_id"] == "op-1"

    def test_from_dict(self):
        d = {
            "checkpoint_id": "chk-123",
            "run_id": "run-456",
            "phase": "before_verification",
            "timestamp": "2024-01-01T00:00:00",
            "state_snapshot": {"step": 3},
            "operation_id": "op-2",
            "metadata": {},
            "integrity_hash": "abc123",
        }
        checkpoint = Checkpoint.from_dict(d)
        assert checkpoint.phase == CheckpointPhase.BEFORE_VERIFICATION
        assert checkpoint.integrity_hash == "abc123"


class TestExecutionRun:
    """Tests for ExecutionRun model."""

    def test_create_run(self):
        run = ExecutionRun(
            run_id="run-123",
            session_id="sess-456",
            task="Write a Python file",
        )
        assert run.run_id == "run-123"
        assert run.status == RunStatus.RUNNING
        assert run.crash_count == 0

    def test_to_dict(self):
        run = ExecutionRun(
            run_id="run-123",
            session_id="sess-456",
            task="Test task",
            status=RunStatus.CRASHED,
            crash_count=2,
        )
        d = run.to_dict()
        assert d["run_id"] == "run-123"
        assert d["status"] == "crashed"
        assert d["crash_count"] == 2

    def test_from_dict(self):
        d = {
            "run_id": "run-123",
            "session_id": "sess-456",
            "task": "Test task",
            "status": "recoverable",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:01:00",
            "completed_at": None,
            "current_phase": "execution",
            "current_step": "write_file",
            "metadata": {},
            "crash_count": 1,
            "resume_count": 0,
            "recovery_budget_used": 3,
            "provider_id": "ollama",
            "approval_scopes": {},
        }
        run = ExecutionRun.from_dict(d)
        assert run.status == RunStatus.RECOVERABLE
        assert run.recovery_budget_used == 3
        assert run.provider_id == "ollama"


class TestLockState:
    """Tests for LockState model."""

    def test_create_lock(self):
        lock = LockState(
            run_id="run-123",
            owner_id="process-1",
        )
        assert lock.run_id == "run-123"
        assert lock.owner_id == "process-1"
        assert lock.state == "acquired"

    def test_to_dict(self):
        lock = LockState(
            run_id="run-123",
            owner_id="process-1",
            state="released",
        )
        d = lock.to_dict()
        assert d["run_id"] == "run-123"
        assert d["state"] == "released"

    def test_from_dict(self):
        d = {
            "run_id": "run-123",
            "owner_id": "process-1",
            "acquired_at": "2024-01-01T00:00:00",
            "expires_at": "2024-01-01T00:05:00",
            "state": "acquired",
            "metadata": {},
        }
        lock = LockState.from_dict(d)
        assert lock.state == "acquired"
        assert lock.expires_at == "2024-01-01T00:05:00"


class TestIdGenerators:
    """Tests for ID generator functions."""

    def test_generate_operation_id(self):
        id1 = generate_operation_id()
        id2 = generate_operation_id()
        assert id1.startswith("op-")
        assert id1 != id2

    def test_generate_run_id(self):
        id1 = generate_run_id()
        id2 = generate_run_id()
        assert id1.startswith("run-")
        assert id1 != id2

    def test_generate_checkpoint_id(self):
        id1 = generate_checkpoint_id()
        id2 = generate_checkpoint_id()
        assert id1.startswith("chk-")
        assert id1 != id2
