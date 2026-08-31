"""ARGUS Durable Execution Integrity Verifier.

Verifies the integrity of snapshots, journals, and checkpoints.
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from argus.durable.models import (
    Checkpoint,
    OperationJournal,
    OperationRecord,
)

logger = logging.getLogger(__name__)


class IntegrityVerifier:
    """Verifies integrity of durable execution data."""

    def verify_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Verify checkpoint integrity."""
        if not checkpoint.integrity_hash:
            logger.error(f"Checkpoint {checkpoint.checkpoint_id} has no integrity hash")
            return False

        expected = self._compute_checkpoint_hash(checkpoint)
        if checkpoint.integrity_hash != expected:
            logger.error(
                f"Checkpoint {checkpoint.checkpoint_id} integrity mismatch: "
                f"expected {expected}, got {checkpoint.integrity_hash}"
            )
            return False

        return True

    def verify_journal(self, journal: OperationJournal) -> Dict[str, Any]:
        """Verify journal integrity.

        Returns:
            Dict with verification results
        """
        results = {
            "valid": True,
            "total_operations": len(journal.operations),
            "invalid_operations": [],
            "warnings": [],
        }

        for op in journal.operations:
            issues = self._verify_operation(op)
            if issues:
                results["valid"] = False
                results["invalid_operations"].append({
                    "operation_id": op.identity.operation_id,
                    "issues": issues,
                })

        # Check for orphaned child operations
        operation_ids = {op.identity.operation_id for op in journal.operations}
        for op in journal.operations:
            for child_id in op.child_operation_ids:
                if child_id not in operation_ids:
                    results["warnings"].append(
                        f"Operation {op.identity.operation_id} references "
                        f"unknown child {child_id}"
                    )

        # Check for parent references
        for op in journal.operations:
            if op.parent_operation_id and op.parent_operation_id not in operation_ids:
                results["warnings"].append(
                    f"Operation {op.identity.operation_id} references "
                    f"unknown parent {op.parent_operation_id}"
                )

        return results

    def verify_snapshot_compatibility(
        self,
        snapshot_version: str,
        current_version: str,
    ) -> bool:
        """Verify snapshot compatibility with current version."""
        # Simple version check - can be expanded
        if not snapshot_version or not current_version:
            return False

        # Major version must match
        snapshot_major = snapshot_version.split(".")[0]
        current_major = current_version.split(".")[0]

        return snapshot_major == current_major

    def verify_event_history_consistency(
        self,
        events: list,
        operations: list,
    ) -> Dict[str, Any]:
        """Verify event history is consistent with operation journal.

        Returns:
            Dict with verification results
        """
        results = {
            "valid": True,
            "missing_events": [],
            "extra_events": [],
            "conflicts": [],
        }

        operation_ids = {op.identity.operation_id for op in operations}
        event_operation_ids = set()

        for event in events:
            op_id = event.get("operation_id")
            if op_id:
                event_operation_ids.add(op_id)
                if op_id not in operation_ids:
                    results["extra_events"].append(op_id)

        for op_id in operation_ids:
            if op_id not in event_operation_ids:
                results["missing_events"].append(op_id)

        if results["missing_events"] or results["extra_events"]:
            results["valid"] = False

        return results

    def detect_corruption(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect data corruption in a dictionary.

        Returns:
            Dict with corruption detection results
        """
        results = {
            "corrupted": False,
            "issues": [],
        }

        # Check for required fields
        if not isinstance(data, dict):
            results["corrupted"] = True
            results["issues"].append("Data is not a dictionary")
            return results

        # Check for null bytes in string values
        self._check_null_bytes(data, "", results)

        return results

    def _check_null_bytes(self, obj: Any, path: str, results: Dict[str, Any]):
        """Recursively check for null bytes in strings."""
        if isinstance(obj, str):
            if "\x00" in obj:
                results["corrupted"] = True
                results["issues"].append(f"Null byte found in {path}")
        elif isinstance(obj, dict):
            for key, value in obj.items():
                self._check_null_bytes(value, f"{path}.{key}", results)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._check_null_bytes(item, f"{path}[{i}]", results)

    def _verify_operation(self, operation: OperationRecord) -> list:
        """Verify an operation record.

        Returns:
            List of issues found (empty if valid)
        """
        issues = []

        if not operation.identity.operation_id:
            issues.append("Missing operation ID")

        if not operation.identity.run_id:
            issues.append("Missing run ID")

        if not operation.created_at:
            issues.append("Missing created_at timestamp")

        if not operation.updated_at:
            issues.append("Missing updated_at timestamp")

        return issues

    def _compute_checkpoint_hash(self, checkpoint: Checkpoint) -> str:
        """Compute integrity hash for a checkpoint."""
        content = json.dumps({
            "checkpoint_id": checkpoint.checkpoint_id,
            "run_id": checkpoint.run_id,
            "phase": checkpoint.phase.value,
            "timestamp": checkpoint.timestamp,
            "state_snapshot": checkpoint.state_snapshot,
            "operation_id": checkpoint.operation_id,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
