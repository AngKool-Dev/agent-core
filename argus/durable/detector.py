"""ARGUS Durable Crash Detection.

Determines the status of runs and detects crashes.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from argus.durable.models import (
    ExecutionRun,
    RunStatus,
)

logger = logging.getLogger(__name__)

RUN_DIR = os.path.join(os.path.expanduser("~"), ".argus", "runs")
HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes


class CrashDetector:
    """Detects crashed runs and determines run status."""

    def __init__(self, run_dir: str = RUN_DIR, heartbeat_timeout: int = HEARTBEAT_TIMEOUT_SECONDS):
        self._run_dir = run_dir
        self._heartbeat_timeout = heartbeat_timeout
        os.makedirs(self._run_dir, exist_ok=True)

    def register_run(self, run: ExecutionRun):
        """Register a new run."""
        self._save_run(run)

    def update_run(self, run: ExecutionRun):
        """Update run metadata."""
        run.updated_at = datetime.utcnow().isoformat()
        self._save_run(run)

    def get_run(self, run_id: str) -> Optional[ExecutionRun]:
        """Get run metadata."""
        path = self._run_path(run_id)
        if not os.path.exists(path):
            return None
        try:
            import json
            with open(path, "r") as f:
                data = json.load(f)
            return ExecutionRun.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load run {run_id}: {e}")
            return None

    def get_all_runs(self) -> List[ExecutionRun]:
        """Get all registered runs."""
        runs = []
        for filename in os.listdir(self._run_dir):
            if filename.endswith(".json"):
                run_id = filename[:-5]
                run = self.get_run(run_id)
                if run:
                    runs.append(run)
        return runs

    def get_active_runs(self) -> List[ExecutionRun]:
        """Get all active (RUNNING) runs."""
        return [r for r in self.get_all_runs() if r.status == RunStatus.RUNNING]

    def get_crashed_runs(self) -> List[ExecutionRun]:
        """Get all crashed runs."""
        return [r for r in self.get_all_runs() if r.status == RunStatus.CRASHED]

    def get_recoverable_runs(self) -> List[ExecutionRun]:
        """Get all recoverable runs."""
        return [r for r in self.get_all_runs() if r.status == RunStatus.RECOVERABLE]

    def detect_crash(self, run_id: str) -> bool:
        """Detect if a run has crashed."""
        run = self.get_run(run_id)
        if not run:
            return False

        if run.status == RunStatus.COMPLETED:
            return False

        if run.status == RunStatus.CRASHED:
            return True

        if run.status == RunStatus.RUNNING:
            # Check heartbeat
            if self._is_heartbeat_stale(run):
                run.status = RunStatus.CRASHED
                run.crash_count += 1
                self._save_run(run)
                logger.warning(f"Run {run_id} detected as crashed (stale heartbeat)")
                return True

        return False

    def mark_crashed(self, run_id: str) -> Optional[ExecutionRun]:
        """Mark a run as crashed."""
        run = self.get_run(run_id)
        if not run:
            return None

        if run.status == RunStatus.COMPLETED:
            logger.warning(f"Cannot mark completed run {run_id} as crashed")
            return run

        run.status = RunStatus.CRASHED
        run.crash_count += 1
        run.updated_at = datetime.utcnow().isoformat()
        self._save_run(run)
        return run

    def mark_recoverable(self, run_id: str) -> Optional[ExecutionRun]:
        """Mark a run as recoverable."""
        run = self.get_run(run_id)
        if not run:
            return None

        if run.status == RunStatus.COMPLETED:
            logger.warning(f"Cannot mark completed run {run_id} as recoverable")
            return run

        run.status = RunStatus.RECOVERABLE
        run.updated_at = datetime.utcnow().isoformat()
        self._save_run(run)
        return run

    def determine_run_status(self, run_id: str) -> Optional[RunStatus]:
        """Determine the current status of a run."""
        run = self.get_run(run_id)
        if not run:
            return None

        if run.status == RunStatus.COMPLETED:
            return RunStatus.COMPLETED

        if run.status == RunStatus.CRASHED:
            return RunStatus.CRASHED

        if run.status == RunStatus.RECOVERABLE:
            return RunStatus.RECOVERABLE

        if run.status == RunStatus.RUNNING:
            if self._is_heartbeat_stale(run):
                self.mark_crashed(run_id)
                return RunStatus.CRASHED
            return RunStatus.RUNNING

        return run.status

    def heartbeat(self, run_id: str) -> Optional[ExecutionRun]:
        """Update the heartbeat for a run."""
        run = self.get_run(run_id)
        if not run:
            return None

        run.metadata["last_heartbeat"] = datetime.utcnow().isoformat()
        run.updated_at = datetime.utcnow().isoformat()
        self._save_run(run)
        return run

    def _is_heartbeat_stale(self, run: ExecutionRun) -> bool:
        """Check if a run's heartbeat is stale."""
        last_heartbeat = run.metadata.get("last_heartbeat")
        if not last_heartbeat:
            # No heartbeat recorded - check updated_at instead
            try:
                last_update = datetime.fromisoformat(run.updated_at)
                return (datetime.utcnow() - last_update).total_seconds() > self._heartbeat_timeout
            except (ValueError, TypeError):
                return True

        try:
            heartbeat_time = datetime.fromisoformat(last_heartbeat)
            return (datetime.utcnow() - heartbeat_time).total_seconds() > self._heartbeat_timeout
        except (ValueError, TypeError):
            return True

    def _save_run(self, run: ExecutionRun):
        """Save run metadata to disk."""
        import json
        path = self._run_path(run.run_id)
        with open(path, "w") as f:
            json.dump(run.to_dict(), f, indent=2)

    def _run_path(self, run_id: str) -> str:
        """Get the file path for a run."""
        return os.path.join(self._run_dir, f"{run_id}.json")
