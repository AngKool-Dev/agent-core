"""ARGUS Durable Execution Lifecycle Manager.

Manages the lifecycle of execution runs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.models import (
    ExecutionRun,
    OperationRecord,
    OperationStatus,
    RunStatus,
    generate_run_id,
)

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages the lifecycle of execution runs.

    States:
    RUNNING -> PAUSED -> CRASHED -> RECOVERABLE -> RECONCILING -> RESUMING -> COMPLETED/FAILED/ABANDONED
    """

    VALID_TRANSITIONS = {
        RunStatus.RUNNING: [RunStatus.PAUSED, RunStatus.CRASHED, RunStatus.COMPLETED, RunStatus.FAILED],
        RunStatus.PAUSED: [RunStatus.RUNNING, RunStatus.ABANDONED],
        RunStatus.CRASHED: [RunStatus.RECOVERABLE, RunStatus.ABANDONED],
        RunStatus.RECOVERABLE: [RunStatus.RECONCILING, RunStatus.ABANDONED],
        RunStatus.RECONCILING: [RunStatus.RESUMING, RunStatus.FAILED, RunStatus.ABANDONED],
        RunStatus.RESUMING: [RunStatus.RUNNING, RunStatus.FAILED],
        RunStatus.COMPLETED: [],  # Terminal state
        RunStatus.FAILED: [],  # Terminal state
        RunStatus.ABANDONED: [],  # Terminal state
    }

    def __init__(
        self,
        detector: CrashDetector = None,
        journal: ExecutionJournal = None,
    ):
        self._detector = detector or CrashDetector()
        self._journal = journal or ExecutionJournal()

    def create_run(
        self,
        session_id: str,
        task: str,
        run_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> ExecutionRun:
        """Create a new execution run."""
        run = ExecutionRun(
            run_id=run_id or generate_run_id(),
            session_id=session_id,
            task=task,
            status=RunStatus.RUNNING,
            metadata=metadata or {},
        )
        self._detector.register_run(run)
        self._journal.create_journal(run.run_id)
        logger.info(f"Created run {run.run_id}")
        return run

    def transition(
        self,
        run_id: str,
        new_status: RunStatus,
    ) -> Optional[ExecutionRun]:
        """Transition a run to a new status.

        Raises:
            ValueError: If the transition is invalid
        """
        run = self._detector.get_run(run_id)
        if not run:
            return None

        if not self.is_valid_transition(run.status, new_status):
            raise ValueError(
                f"Invalid transition: {run.status.value} -> {new_status.value}"
            )

        old_status = run.status
        run.status = new_status
        run.updated_at = datetime.utcnow().isoformat()

        if new_status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABANDONED):
            run.completed_at = datetime.utcnow().isoformat()

        self._detector.update_run(run)
        logger.info(f"Run {run_id}: {old_status.value} -> {new_status.value}")
        return run

    def is_valid_transition(self, from_status: RunStatus, to_status: RunStatus) -> bool:
        """Check if a status transition is valid."""
        valid_next = self.VALID_TRANSITIONS.get(from_status, [])
        return to_status in valid_next

    def can_resume(self, run_id: str) -> bool:
        """Check if a run can be resumed."""
        run = self._detector.get_run(run_id)
        if not run:
            return False
        return run.status in (RunStatus.CRASHED, RunStatus.RECOVERABLE)

    def is_terminal(self, run_id: str) -> bool:
        """Check if a run is in a terminal state."""
        run = self._detector.get_run(run_id)
        if not run:
            return False
        return run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABANDONED)

    def get_run(self, run_id: str) -> Optional[ExecutionRun]:
        """Get a run by ID."""
        return self._detector.get_run(run_id)

    def get_all_runs(self) -> List[ExecutionRun]:
        """Get all runs."""
        return self._detector.get_all_runs()

    def get_runs_by_status(self, status: RunStatus) -> List[ExecutionRun]:
        """Get all runs with a given status."""
        return [r for r in self.get_all_runs() if r.status == status]

    def cleanup_run(self, run_id: str):
        """Clean up a completed/failed/abandoned run."""
        run = self._detector.get_run(run_id)
        if not run:
            return

        if run.status not in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ABANDONED):
            logger.warning(f"Cannot cleanup run {run_id} with status {run.status.value}")
            return

        # Journal and run metadata are kept for forensics
        logger.info(f"Run {run_id} cleaned up")
