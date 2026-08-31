"""ARGUS Durable Resume Engine.

Orchestrates crash recovery and safe resume of execution.
"""

import logging
from typing import Any, Dict, List, Optional

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.models import (
    ExecutionRun,
    OperationRecord,
    OperationStatus,
    OperationType,
    ReconciliationDecision,
    ResumeMode,
    RunStatus,
)
from argus.durable.reconciler import Reconciler

logger = logging.getLogger(__name__)


class ResumeEngine:
    """Engine for resuming crashed runs.

    Responsibilities:
    - Load run
    - Validate integrity
    - Load snapshot and journal
    - Reconstruct state
    - Identify incomplete operations
    - Reconcile UNKNOWN operations
    - Restore recovery budget
    - Restore security context
    - Continue execution
    """

    def __init__(
        self,
        journal: ExecutionJournal = None,
        detector: CrashDetector = None,
        reconciler: Reconciler = None,
    ):
        self._journal = journal or ExecutionJournal()
        self._detector = detector or CrashDetector()
        self._reconciler = reconciler or Reconciler()

    def analyze_run(self, run_id: str) -> Dict[str, Any]:
        """Analyze a run for resumability.

        Returns:
            Dict with analysis results
        """
        run = self._detector.get_run(run_id)
        if not run:
            return {"error": f"Run {run_id} not found"}

        journal = self._journal.get_journal(run_id)
        unknown_ops = journal.get_unknown_operations() if journal else []
        started_ops = journal.get_operations_by_status(OperationStatus.STARTED) if journal else []
        completed_ops = journal.get_operations_by_status(OperationStatus.COMPLETED) if journal else []
        failed_ops = journal.get_operations_by_status(OperationStatus.FAILED) if journal else []

        return {
            "run_id": run_id,
            "status": run.status.value,
            "can_resume": run.status in (RunStatus.CRASHED, RunStatus.RECOVERABLE),
            "unknown_operations": len(unknown_ops),
            "started_operations": len(started_ops),
            "completed_operations": len(completed_ops),
            "failed_operations": len(failed_ops),
            "crash_count": run.crash_count,
            "recovery_budget_used": run.recovery_budget_used,
            "current_phase": run.current_phase,
        }

    def dry_run_resume(self, run_id: str) -> Dict[str, Any]:
        """Perform a dry-run resume (no execution).

        Returns:
            Dict with planned resume actions
        """
        analysis = self.analyze_run(run_id)
        if "error" in analysis:
            return analysis

        journal = self._journal.get_journal(run_id)
        if not journal:
            return {"error": f"No journal found for run {run_id}"}

        unknown_ops = journal.get_unknown_operations()
        reconciliation_plans = []

        for op in unknown_ops:
            decision, status, details = self._reconciler.reconcile(op)
            reconciliation_plans.append({
                "operation_id": op.identity.operation_id,
                "operation_type": op.identity.operation_type.value,
                "target": op.identity.target,
                "decision": decision.value,
                "planned_status": status.value,
                "details": details,
            })

        analysis["reconciliation_plans"] = reconciliation_plans
        analysis["total_reconciliations"] = len(reconciliation_plans)
        analysis["safe_retries"] = sum(
            1 for p in reconciliation_plans if p["decision"] == "retry"
        )
        analysis["requires_user"] = sum(
            1 for p in reconciliation_plans if p["decision"] == "require_user"
        )
        analysis["mark_completed"] = sum(
            1 for p in reconciliation_plans if p["decision"] == "mark_completed"
        )

        return analysis

    def resume(
        self,
        run_id: str,
        mode: ResumeMode = ResumeMode.NORMAL,
    ) -> Dict[str, Any]:
        """Resume a crashed run.

        Args:
            run_id: The run to resume
            mode: Resume mode (NORMAL, DRY_RUN, RECONCILE)

        Returns:
            Dict with resume results
        """
        run = self._detector.get_run(run_id)
        if not run:
            return {"success": False, "error": f"Run {run_id} not found"}

        if run.status not in (RunStatus.CRASHED, RunStatus.RECOVERABLE):
            return {
                "success": False,
                "error": f"Run {run_id} is not in a resumable state (status: {run.status.value})",
            }

        # Mark as reconciling
        run.status = RunStatus.RECONCILING
        self._detector.update_run(run)

        # Reconcile UNKNOWN operations
        reconciliation_results = self._reconcile_unknown_operations(run_id)

        # Check for operations requiring user decision
        requires_user = [
            r for r in reconciliation_results
            if r["decision"] == ReconciliationDecision.REQUIRE_USER
        ]

        if requires_user and mode != ResumeMode.RECONCILE:
            run.status = RunStatus.RECOVERABLE
            self._detector.update_run(run)
            return {
                "success": False,
                "requires_user_decision": True,
                "operations_requiring_decision": requires_user,
                "message": "Some operations require user decision before resume",
            }

        # Mark as resuming
        run.status = RunStatus.RESUMING
        run.resume_count += 1
        self._detector.update_run(run)

        if mode == ResumeMode.DRY_RUN:
            run.status = RunStatus.RECOVERABLE
            self._detector.update_run(run)
            return {
                "success": True,
                "dry_run": True,
                "reconciliation_results": reconciliation_results,
            }

        # Normal resume - mark run as running
        run.status = RunStatus.RUNNING
        self._detector.update_run(run)

        return {
            "success": True,
            "dry_run": False,
            "reconciliation_results": reconciliation_results,
            "message": "Run resumed successfully",
        }

    def _reconcile_unknown_operations(
        self,
        run_id: str,
    ) -> List[Dict[str, Any]]:
        """Reconcile all UNKNOWN operations."""
        unknown_ops = self._journal.get_unknown_operations(run_id)
        results = []

        for op in unknown_ops:
            decision, status, details = self._reconciler.reconcile(op)

            # Record the reconciliation decision
            self._journal.record_reconciliation(
                run_id=run_id,
                operation_id=op.identity.operation_id,
                decision=decision.value,
                final_status=status,
            )

            results.append({
                "operation_id": op.identity.operation_id,
                "operation_type": op.identity.operation_type.value,
                "decision": decision,
                "final_status": status,
                "details": details,
            })

        return results

    def get_resume_plan(self, run_id: str) -> Dict[str, Any]:
        """Get the resume plan for a run without executing it."""
        analysis = self.analyze_run(run_id)
        if "error" in analysis:
            return analysis

        dry_run = self.dry_run_resume(run_id)
        return dry_run

    def mark_run_completed(self, run_id: str) -> Optional[ExecutionRun]:
        """Mark a run as completed."""
        run = self._detector.get_run(run_id)
        if not run:
            return None

        if run.status == RunStatus.COMPLETED:
            return run

        from datetime import datetime
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.utcnow().isoformat()
        run.updated_at = datetime.utcnow().isoformat()
        self._detector.update_run(run)
        return run

    def mark_run_failed(self, run_id: str) -> Optional[ExecutionRun]:
        """Mark a run as failed."""
        run = self._detector.get_run(run_id)
        if not run:
            return None

        if run.status == RunStatus.COMPLETED:
            return run

        from datetime import datetime
        run.status = RunStatus.FAILED
        run.completed_at = datetime.utcnow().isoformat()
        run.updated_at = datetime.utcnow().isoformat()
        self._detector.update_run(run)
        return run

    def mark_run_abandoned(self, run_id: str) -> Optional[ExecutionRun]:
        """Mark a run as abandoned."""
        run = self._detector.get_run(run_id)
        if not run:
            return None

        from datetime import datetime
        run.status = RunStatus.ABANDONED
        run.completed_at = datetime.utcnow().isoformat()
        run.updated_at = datetime.utcnow().isoformat()
        self._detector.update_run(run)
        return run
