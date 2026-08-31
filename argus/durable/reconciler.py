"""ARGUS Durable Execution Reconciler.

Handles UNKNOWN operations after a crash.
Never silently guesses - inspects observable state.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from argus.durable.models import (
    IdempotencyClass,
    OperationRecord,
    OperationStatus,
    OperationType,
    ReconciliationDecision,
    RetryPolicy,
)

logger = logging.getLogger(__name__)


class Reconciler:
    """Reconciles UNKNOWN operations after a crash.

    For each UNKNOWN operation, the reconciler:
    1. Inspects observable state
    2. Determines if the operation completed, did not execute, or is ambiguous
    3. Makes a reconciliation decision
    """

    def __init__(self):
        self._evidence_collectors: Dict[OperationType, Callable] = {}
        self._register_default_collectors()

    def register_evidence_collector(
        self,
        operation_type: OperationType,
        collector: Callable[[OperationRecord], Dict[str, Any]],
    ):
        """Register an evidence collector for an operation type."""
        self._evidence_collectors[operation_type] = collector

    def reconcile(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any] = None,
    ) -> tuple:
        """Reconcile an UNKNOWN operation.

        Returns:
            Tuple of (ReconciliationDecision, OperationStatus, details)
        """
        if operation.status != OperationStatus.UNKNOWN:
            return (
                ReconciliationDecision.SKIP,
                operation.status,
                "Operation is not UNKNOWN",
            )

        # Collect evidence if not provided
        if evidence is None:
            evidence = self._collect_evidence(operation)

        # Analyze evidence
        return self._analyze_evidence(operation, evidence)

    def reconcile_all(
        self,
        operations: List[OperationRecord],
    ) -> List[tuple]:
        """Reconcile all UNKNOWN operations.

        Returns:
            List of (operation, decision, final_status, details) tuples
        """
        results = []
        for op in operations:
            if op.status == OperationStatus.UNKNOWN:
                decision, status, details = self.reconcile(op)
                results.append((op, decision, status, details))
        return results

    def _collect_evidence(self, operation: OperationRecord) -> Dict[str, Any]:
        """Collect evidence about an operation's outcome."""
        evidence = {
            "operation_id": operation.identity.operation_id,
            "operation_type": operation.identity.operation_type.value,
            "target": operation.identity.target,
        }

        # Use registered collector if available
        collector = self._evidence_collectors.get(operation.identity.operation_type)
        if collector:
            try:
                collected = collector(operation)
                evidence.update(collected)
            except Exception as e:
                logger.warning(f"Evidence collection failed for {operation.identity.operation_id}: {e}")
                evidence["collection_error"] = str(e)

        return evidence

    def _analyze_evidence(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze evidence and make a reconciliation decision."""
        op_type = operation.identity.operation_type

        # Check for collection errors
        if "collection_error" in evidence:
            return (
                ReconciliationDecision.REQUIRE_USER,
                OperationStatus.REQUIRES_DECISION,
                f"Evidence collection failed: {evidence['collection_error']}",
            )

        # File system operations
        if op_type == OperationType.FILESYSTEM_WRITE:
            return self._analyze_filesystem_write(operation, evidence)
        elif op_type == OperationType.FILESYSTEM_READ:
            return self._analyze_filesystem_read(operation, evidence)
        elif op_type == OperationType.FILESYSTEM_DELETE:
            return self._analyze_filesystem_delete(operation, evidence)

        # Shell operations
        elif op_type == OperationType.SHELL_EXECUTE:
            return self._analyze_shell_execute(operation, evidence)

        # Git operations
        elif op_type == OperationType.GIT_OPERATION:
            return self._analyze_git_operation(operation, evidence)

        # MCP operations
        elif op_type == OperationType.MCP_TOOL:
            return self._analyze_mcp_tool(operation, evidence)

        # Model calls
        elif op_type == OperationType.MODEL_CALL:
            return self._analyze_model_call(operation, evidence)

        # Verification/Recovery/Review
        elif op_type in (OperationType.VERIFICATION, OperationType.RECOVERY, OperationType.REVIEW):
            return self._analyze_phase_operation(operation, evidence)

        # Default: require user decision for unknown operation types
        return (
            ReconciliationDecision.REQUIRE_USER,
            OperationStatus.REQUIRES_DECISION,
            f"Cannot automatically reconcile {op_type.value}",
        )

    def _analyze_filesystem_write(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze a filesystem write operation."""
        file_exists = evidence.get("file_exists", False)
        content_matches = evidence.get("content_matches", False)
        write_completed = evidence.get("write_completed", False)

        if write_completed and file_exists and content_matches:
            return (
                ReconciliationDecision.MARK_COMPLETED,
                OperationStatus.RECONCILED_COMPLETED,
                "File exists with matching content",
            )

        if not file_exists:
            return (
                ReconciliationDecision.RETRY,
                OperationStatus.RECONCILED_NOT_EXECUTED,
                "File does not exist - safe to retry",
            )

        if file_exists and not content_matches:
            return (
                ReconciliationDecision.REQUIRE_USER,
                OperationStatus.REQUIRES_DECISION,
                "File exists but content does not match",
            )

        return (
            ReconciliationDecision.REQUIRE_USER,
            OperationStatus.REQUIRES_DECISION,
            "Cannot determine write status",
        )

    def _analyze_filesystem_read(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze a filesystem read operation."""
        # Reads are idempotent - always safe to retry
        return (
            ReconciliationDecision.RETRY,
            OperationStatus.RECONCILED_NOT_EXECUTED,
            "Read operation is idempotent - safe to retry",
        )

    def _analyze_filesystem_delete(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze a filesystem delete operation."""
        file_exists = evidence.get("file_exists", True)
        delete_completed = evidence.get("delete_completed", False)

        if delete_completed or not file_exists:
            return (
                ReconciliationDecision.MARK_COMPLETED,
                OperationStatus.RECONCILED_COMPLETED,
                "File does not exist - delete completed",
            )

        return (
            ReconciliationDecision.RETRY,
            OperationStatus.RECONCILED_NOT_EXECUTED,
            "File still exists - safe to retry delete",
        )

    def _analyze_shell_execute(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze a shell execution operation."""
        # Shell commands are generally not idempotent
        # Check for side effects
        side_effects_detected = evidence.get("side_effects_detected", None)

        if side_effects_detected is True:
            return (
                ReconciliationDecision.REQUIRE_USER,
                OperationStatus.REQUIRES_DECISION,
                "Shell command may have had side effects",
            )

        if side_effects_detected is False:
            return (
                ReconciliationDecision.RETRY,
                OperationStatus.RECONCILED_NOT_EXECUTED,
                "No side effects detected - safe to retry",
            )

        return (
            ReconciliationDecision.REQUIRE_USER,
            OperationStatus.REQUIRES_DECISION,
            "Cannot determine shell command side effects",
        )

    def _analyze_git_operation(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze a git operation."""
        operation_completed = evidence.get("operation_completed", False)
        expected_state_matches = evidence.get("expected_state_matches", None)

        if operation_completed and expected_state_matches:
            return (
                ReconciliationDecision.MARK_COMPLETED,
                OperationStatus.RECONCILED_COMPLETED,
                "Git operation completed - state matches expected",
            )

        if expected_state_matches is False:
            return (
                ReconciliationDecision.RETRY,
                OperationStatus.RECONCILED_NOT_EXECUTED,
                "Git state does not match - safe to retry",
            )

        return (
            ReconciliationDecision.REQUIRE_USER,
            OperationStatus.REQUIRES_DECISION,
            "Cannot determine git operation status",
        )

    def _analyze_mcp_tool(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze an MCP tool call."""
        # MCP tool calls may be non-idempotent
        call_completed = evidence.get("call_completed", False)
        response_received = evidence.get("response_received", False)

        if call_completed and response_received:
            return (
                ReconciliationDecision.MARK_COMPLETED,
                OperationStatus.RECONCILED_COMPLETED,
                "MCP call completed with response",
            )

        return (
            ReconciliationDecision.REQUIRE_USER,
            OperationStatus.REQUIRES_DECISION,
            "MCP call status unknown - cannot safely retry",
        )

    def _analyze_model_call(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze a model call."""
        # Model calls are generally idempotent (same input -> same output)
        response_received = evidence.get("response_received", False)

        if response_received:
            return (
                ReconciliationDecision.MARK_COMPLETED,
                OperationStatus.RECONCILED_COMPLETED,
                "Model call completed with response",
            )

        return (
            ReconciliationDecision.RETRY,
            OperationStatus.RECONCILED_NOT_EXECUTED,
            "Model call is idempotent - safe to retry",
        )

    def _analyze_phase_operation(
        self,
        operation: OperationRecord,
        evidence: Dict[str, Any],
    ) -> tuple:
        """Analyze verification/recovery/review operations."""
        phase_completed = evidence.get("phase_completed", False)

        if phase_completed:
            return (
                ReconciliationDecision.MARK_COMPLETED,
                OperationStatus.RECONCILED_COMPLETED,
                "Phase completed",
            )

        return (
            ReconciliationDecision.RETRY,
            OperationStatus.RECONCILED_NOT_EXECUTED,
            "Phase incomplete - safe to retry",
        )

    def _register_default_collectors(self):
        """Register default evidence collectors."""
        self._evidence_collectors[OperationType.FILESYSTEM_WRITE] = self._collect_filesystem_write_evidence
        self._evidence_collectors[OperationType.FILESYSTEM_READ] = self._collect_filesystem_read_evidence
        self._evidence_collectors[OperationType.FILESYSTEM_DELETE] = self._collect_filesystem_delete_evidence

    def _collect_filesystem_write_evidence(
        self, operation: OperationRecord
    ) -> Dict[str, Any]:
        """Collect evidence for a filesystem write operation."""
        import os
        target = operation.identity.target
        expected_content = operation.identity.normalized_arguments.get("content", "")

        evidence = {"file_exists": False, "content_matches": False, "write_completed": False}

        if os.path.exists(target):
            evidence["file_exists"] = True
            try:
                with open(target, "r") as f:
                    actual_content = f.read()
                evidence["content_matches"] = actual_content == expected_content
                evidence["write_completed"] = True
            except IOError:
                pass

        return evidence

    def _collect_filesystem_read_evidence(
        self, operation: OperationRecord
    ) -> Dict[str, Any]:
        """Collect evidence for a filesystem read operation."""
        import os
        target = operation.identity.target
        return {"file_exists": os.path.exists(target)}

    def _collect_filesystem_delete_evidence(
        self, operation: OperationRecord
    ) -> Dict[str, Any]:
        """Collect evidence for a filesystem delete operation."""
        import os
        target = operation.identity.target
        return {
            "file_exists": os.path.exists(target),
            "delete_completed": not os.path.exists(target),
        }
