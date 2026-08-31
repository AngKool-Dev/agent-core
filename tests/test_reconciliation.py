"""Tests for ARGUS Durable reconciliation."""

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
)
from argus.durable.reconciler import Reconciler


class TestReconciler:
    """Tests for Reconciler."""

    def test_reconcile_non_unknown(self):
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_READ,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.COMPLETED,
        )
        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.SKIP
        assert status == OperationStatus.COMPLETED

    def test_reconcile_filesystem_read(self):
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_READ,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.RETRY
        assert status == OperationStatus.RECONCILED_NOT_EXECUTED

    def test_reconcile_filesystem_write_completed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("hello world")

            reconciler = Reconciler()
            identity = OperationIdentity(
                operation_id="op-1",
                run_id="run-1",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_WRITE,
                target=test_file,
                normalized_arguments={"content": "hello world"},
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.UNKNOWN,
            )
            decision, status, details = reconciler.reconcile(record)
            assert decision == ReconciliationDecision.MARK_COMPLETED
            assert status == OperationStatus.RECONCILED_COMPLETED

    def test_reconcile_filesystem_write_not_executed(self):
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/nonexistent/path/test.py",
            normalized_arguments={"content": "hello"},
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.RETRY
        assert status == OperationStatus.RECONCILED_NOT_EXECUTED

    def test_reconcile_filesystem_write_content_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("different content")

            reconciler = Reconciler()
            identity = OperationIdentity(
                operation_id="op-1",
                run_id="run-1",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_WRITE,
                target=test_file,
                normalized_arguments={"content": "expected content"},
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.UNKNOWN,
            )
            decision, status, details = reconciler.reconcile(record)
            assert decision == ReconciliationDecision.REQUIRE_USER
            assert status == OperationStatus.REQUIRES_DECISION

    def test_reconcile_filesystem_delete_completed(self):
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_DELETE,
            target="/nonexistent/file.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.MARK_COMPLETED

    def test_reconcile_filesystem_delete_not_executed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("content")

            reconciler = Reconciler()
            identity = OperationIdentity(
                operation_id="op-1",
                run_id="run-1",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_DELETE,
                target=test_file,
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.UNKNOWN,
            )
            decision, status, details = reconciler.reconcile(record)
            assert decision == ReconciliationDecision.RETRY

    def test_reconcile_shell_execute_unknown_side_effects(self):
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
        assert decision == ReconciliationDecision.REQUIRE_USER

    def test_reconcile_model_call(self):
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.MODEL_CALL,
            target="ollama/llama3",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.RETRY

    def test_reconcile_mcp_tool(self):
        reconciler = Reconciler()
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-1",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.MCP_TOOL,
            target="read_file",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.UNKNOWN,
        )
        decision, status, details = reconciler.reconcile(record)
        assert decision == ReconciliationDecision.REQUIRE_USER

    def test_reconcile_all(self):
        reconciler = Reconciler()
        operations = []
        for op_type, target in [
            (OperationType.FILESYSTEM_READ, "/workspace/test.py"),
            (OperationType.FILESYSTEM_WRITE, "/nonexistent/test.py"),
            (OperationType.MODEL_CALL, "ollama/llama3"),
        ]:
            identity = OperationIdentity(
                operation_id=f"op-{op_type.value}",
                run_id="run-1",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=op_type,
                target=target,
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.UNKNOWN,
            )
            operations.append(record)

        results = reconciler.reconcile_all(operations)
        assert len(results) == 3

    def test_register_evidence_collector(self):
        reconciler = Reconciler()
        collector = lambda op: {"custom": "evidence"}
        reconciler.register_evidence_collector(OperationType.SHELL_EXECUTE, collector)
        assert OperationType.SHELL_EXECUTE in reconciler._evidence_collectors


class TestIdempotencyClassifier:
    """Tests for IdempotencyClassifier."""

    def test_classify_filesystem_read(self):
        classifier = IdempotencyClassifier()
        assert classifier.classify(OperationType.FILESYSTEM_READ) == IdempotencyClass.IDEMPOTENT

    def test_classify_filesystem_write(self):
        classifier = IdempotencyClassifier()
        assert classifier.classify(OperationType.FILESYSTEM_WRITE) == IdempotencyClass.CONDITIONALLY_IDEMPOTENT

    def test_classify_shell_execute(self):
        classifier = IdempotencyClassifier()
        assert classifier.classify(OperationType.SHELL_EXECUTE) == IdempotencyClass.NON_IDEMPOTENT

    def test_classify_mcp_tool(self):
        classifier = IdempotencyClassifier()
        assert classifier.classify(OperationType.MCP_TOOL) == IdempotencyClass.UNKNOWN

    def test_is_idempotent(self):
        classifier = IdempotencyClassifier()
        assert classifier.is_idempotent(OperationType.FILESYSTEM_READ)
        assert not classifier.is_idempotent(OperationType.SHELL_EXECUTE)

    def test_determine_retry_policy(self):
        classifier = IdempotencyClassifier()
        assert classifier.determine_retry_policy(OperationType.FILESYSTEM_READ) == RetryPolicy.SAFE_RETRY
        assert classifier.determine_retry_policy(OperationType.SHELL_EXECUTE) == RetryPolicy.UNSAFE_RETRY
        assert classifier.determine_retry_policy(OperationType.MCP_TOOL) == RetryPolicy.USER_DECISION

    def test_set_classification(self):
        classifier = IdempotencyClassifier()
        classifier.set_classification(OperationType.MCP_TOOL, IdempotencyClass.IDEMPOTENT)
        assert classifier.classify(OperationType.MCP_TOOL) == IdempotencyClass.IDEMPOTENT

    def test_get_all_classifications(self):
        classifier = IdempotencyClassifier()
        classifications = classifier.get_all_classifications()
        assert "filesystem.read" in classifications
        assert classifications["filesystem.read"] == "idempotent"
        assert classifications["shell.execute"] == "non_idempotent"
