"""ARGUS Durable Execution Reporting.

Generates reports for crash/resume operations.
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

logger = logging.getLogger(__name__)


class DurableReporter:
    """Generates durable execution reports."""

    def __init__(
        self,
        detector: CrashDetector = None,
        journal: ExecutionJournal = None,
    ):
        self._detector = detector or CrashDetector()
        self._journal = journal or ExecutionJournal()

    def generate_run_report(self, run_id: str) -> str:
        """Generate a report for a run."""
        run = self._detector.get_run(run_id)
        if not run:
            return f"Run {run_id} not found"

        journal = self._journal.get_journal(run_id)
        operations = journal.operations if journal else []

        unknown = [op for op in operations if op.status == OperationStatus.UNKNOWN]
        completed = [op for op in operations if op.status == OperationStatus.COMPLETED]
        failed = [op for op in operations if op.status == OperationStatus.FAILED]
        started = [op for op in operations if op.status == OperationStatus.STARTED]

        lines = [
            "ARGUS DURABLE EXECUTION REPORT",
            "=" * 60,
            f"Run ID: {run.run_id}",
            f"Session: {run.session_id}",
            f"Task: {run.task}",
            f"Status: {run.status.value}",
            f"Created: {run.created_at}",
            f"Updated: {run.updated_at}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Operations: {len(operations)}",
            f"Completed: {len(completed)}",
            f"Failed: {len(failed)}",
            f"Started (incomplete): {len(started)}",
            f"Unknown: {len(unknown)}",
            "",
            "CRASH/RESUME",
            "-" * 40,
            f"Crash Count: {run.crash_count}",
            f"Resume Count: {run.resume_count}",
            f"Recovery Budget Used: {run.recovery_budget_used}",
            "",
        ]

        if unknown:
            lines.append("UNKNOWN OPERATIONS")
            lines.append("-" * 40)
            for op in unknown:
                lines.append(f"  {op.identity.operation_id}: {op.identity.operation_type.value}")
                lines.append(f"    Target: {op.identity.target}")
                lines.append(f"    Started: {op.created_at}")
            lines.append("")

        if failed:
            lines.append("FAILED OPERATIONS")
            lines.append("-" * 40)
            for op in failed:
                lines.append(f"  {op.identity.operation_id}: {op.identity.operation_type.value}")
                lines.append(f"    Error: {op.error}")
            lines.append("")

        return "\n".join(lines)

    def generate_json_report(self, run_id: str) -> Dict[str, Any]:
        """Generate a JSON report for a run."""
        run = self._detector.get_run(run_id)
        if not run:
            return {"error": f"Run {run_id} not found"}

        journal = self._journal.get_journal(run_id)
        operations = journal.operations if journal else []

        return {
            "run": run.to_dict(),
            "operations": {
                "total": len(operations),
                "by_status": self._count_by_status(operations),
                "unknown": [
                    op.to_dict() for op in operations
                    if op.status == OperationStatus.UNKNOWN
                ],
                "failed": [
                    op.to_dict() for op in operations
                    if op.status == OperationStatus.FAILED
                ],
            },
        }

    def generate_system_report(self) -> str:
        """Generate a system-wide report."""
        runs = self._detector.get_all_runs()

        running = [r for r in runs if r.status == RunStatus.RUNNING]
        crashed = [r for r in runs if r.status == RunStatus.CRASHED]
        recoverable = [r for r in runs if r.status == RunStatus.RECOVERABLE]
        completed = [r for r in runs if r.status == RunStatus.COMPLETED]
        failed = [r for r in runs if r.status == RunStatus.FAILED]

        lines = [
            "ARGUS DURABLE EXECUTION SYSTEM REPORT",
            "=" * 60,
            f"Total Runs: {len(runs)}",
            "",
            "RUNS BY STATUS",
            "-" * 40,
            f"Running: {len(running)}",
            f"Crashed: {len(crashed)}",
            f"Recoverable: {len(recoverable)}",
            f"Completed: {len(completed)}",
            f"Failed: {len(failed)}",
            "",
        ]

        if crashed:
            lines.append("CRASHED RUNS")
            lines.append("-" * 40)
            for run in crashed:
                lines.append(f"  {run.run_id}: {run.task} (crashes: {run.crash_count})")
            lines.append("")

        if recoverable:
            lines.append("RECOVERABLE RUNS")
            lines.append("-" * 40)
            for run in recoverable:
                lines.append(f"  {run.run_id}: {run.task} (crashes: {run.crash_count})")
            lines.append("")

        return "\n".join(lines)

    def _count_by_status(self, operations: List[OperationRecord]) -> Dict[str, int]:
        """Count operations by status."""
        counts: Dict[str, int] = {}
        for op in operations:
            status = op.status.value
            counts[status] = counts.get(status, 0) + 1
        return counts
