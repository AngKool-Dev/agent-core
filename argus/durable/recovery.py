"""ARGUS Durable Crash Recovery.

Integrates with existing recovery engine for crash recovery.
"""

import logging
from typing import Any, Dict, List, Optional

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.models import (
    ExecutionRun,
    OperationRecord,
    OperationStatus,
    RunStatus,
)
from argus.durable.resume import ResumeEngine

logger = logging.getLogger(__name__)


class CrashRecovery:
    """Manages crash recovery operations.

    Integrates with the existing RecoveryEngine for:
    - Recovery budget persistence
    - Failure history restoration
    - Strategy context restoration
    """

    def __init__(
        self,
        detector: CrashDetector = None,
        journal: ExecutionJournal = None,
        resume_engine: ResumeEngine = None,
    ):
        self._detector = detector or CrashDetector()
        self._journal = journal or ExecutionJournal()
        self._resume_engine = resume_engine or ResumeEngine(
            journal=self._journal, detector=self._detector
        )

    def detect_and_recover(self, run_id: str) -> Dict[str, Any]:
        """Detect crash and initiate recovery.

        Returns:
            Dict with recovery results
        """
        run = self._detector.get_run(run_id)
        if not run:
            return {"error": f"Run {run_id} not found"}

        # Check if already crashed
        if run.status == RunStatus.CRASHED:
            return self._handle_crashed_run(run)

        # Detect crash
        if self._detector.detect_crash(run_id):
            return self._handle_crashed_run(run)

        return {"status": "no_crash_detected", "run_status": run.status.value}

    def _handle_crashed_run(self, run: ExecutionRun) -> Dict[str, Any]:
        """Handle a crashed run."""
        # Mark all STARTED operations as UNKNOWN
        unknown_ops = self._journal.mark_all_started_as_unknown(run.run_id)

        # Mark run as recoverable
        self._detector.mark_recoverable(run.run_id)

        return {
            "status": "crash_detected",
            "run_id": run.run_id,
            "unknown_operations": len(unknown_ops),
            "crash_count": run.crash_count,
            "message": "Run marked as recoverable",
        }

    def restore_recovery_budget(
        self,
        run_id: str,
        budget_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Restore recovery budget after crash.

        The budget must survive process death.

        Args:
            run_id: The run ID
            budget_state: The budget state to restore

        Returns:
            Dict with restored budget info
        """
        run = self._detector.get_run(run_id)
        if not run:
            return {"error": f"Run {run_id} not found"}

        # Restore used attempts
        used_attempts = budget_state.get("attempts", 0)
        run.recovery_budget_used = used_attempts
        self._detector.update_run(run)

        return {
            "status": "budget_restored",
            "run_id": run_id,
            "used_attempts": used_attempts,
        }

    def get_recovery_budget_state(self, run_id: str) -> Dict[str, Any]:
        """Get the current recovery budget state for persistence."""
        run = self._detector.get_run(run_id)
        if not run:
            return {}

        return {
            "run_id": run_id,
            "attempts": run.recovery_budget_used,
            "crash_count": run.crash_count,
            "resume_count": run.resume_count,
        }

    def can_continue_recovery(self, run_id: str, max_crashes: int = 3) -> bool:
        """Check if recovery can continue (budget not exhausted)."""
        run = self._detector.get_run(run_id)
        if not run:
            return False

        return run.crash_count <= max_crashes

    def get_failure_history(
        self,
        run_id: str,
    ) -> List[Dict[str, Any]]:
        """Get the failure history for a run."""
        failed_ops = self._journal.get_operations_by_status(run_id, OperationStatus.FAILED)
        return [
            {
                "operation_id": op.identity.operation_id,
                "operation_type": op.identity.operation_type.value,
                "error": op.error,
                "timestamp": op.updated_at,
            }
            for op in failed_ops
        ]
