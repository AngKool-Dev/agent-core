"""ARGUS Replay engine - core replay orchestration."""

import copy
import logging
from typing import Any, Dict, List, Optional

from argus.replay.models import (
    ReplayRun,
    RunStatus,
)
from argus.replay.loader import ReplayLoader
from argus.replay.timeline import ReplayTimeline
from argus.replay.reducer import StateReducer
from argus.replay.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)


class ReplayResult:
    """Result of a replay operation."""

    def __init__(
        self,
        run_id: str,
        status: RunStatus,
        timeline: List[Any],
        execution_tree: Optional[Dict[str, Any]],
        final_state: Optional[Dict[str, Any]],
        consistency_issues: List[Any],
        event_count: int = 0,
        duration: Optional[float] = None,
    ):
        self.run_id = run_id
        self.status = status
        self.timeline = timeline
        self.execution_tree = execution_tree
        self.final_state = final_state
        self.consistency_issues = consistency_issues
        self.event_count = event_count
        self.duration = duration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "event_count": self.event_count,
            "duration": self.duration,
            "timeline_length": len(self.timeline),
            "has_execution_tree": self.execution_tree is not None,
            "has_final_state": self.final_state is not None,
            "consistency_issues_count": len(self.consistency_issues),
            "consistency_issues": [i.to_dict() if hasattr(i, "to_dict") else str(i) for i in self.consistency_issues],
        }


class ReplayEngine:
    """Core replay engine for reconstructing ARGUS runs.

    IMPORTANT: This engine is observational only.
    It NEVER executes tools, calls models, or mutates production state.
    """

    def __init__(self):
        self._loader = ReplayLoader()
        self._runs: Dict[str, ReplayRun] = {}

    def load_run(self, run_id: str) -> ReplayRun:
        """Load a run for replay.

        Args:
            run_id: The run ID to load

        Returns:
            The loaded ReplayRun
        """
        run = self._loader.load(run_id)
        self._runs[run_id] = run
        return run

    def load_partial_run(self, run_id: str, events: List[Dict]) -> ReplayRun:
        """Load a partial run from events.

        Args:
            run_id: The run ID
            events: List of event dictionaries

        Returns:
            The loaded ReplayRun
        """
        run = self._loader.load_partial(run_id, events)
        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> Optional[ReplayRun]:
        """Get a previously loaded run."""
        return self._runs.get(run_id)

    def get_timeline(self, run_id: str) -> Optional[ReplayTimeline]:
        """Get the timeline for a run."""
        run = self.get_run(run_id)
        if run:
            return ReplayTimeline(run)
        return None

    def get_checkpoint_manager(self, run_id: str) -> Optional[CheckpointManager]:
        """Get the checkpoint manager for a run."""
        run = self.get_run(run_id)
        if run:
            return CheckpointManager(run)
        return None

    def reconstruct_state(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Reconstruct the final state of a run.

        Args:
            run_id: The run ID

        Returns:
            The reconstructed final state
        """
        run = self.get_run(run_id)
        if run:
            reducer = StateReducer()
            return reducer.reduce(run)
        return None

    def reconstruct_state_at(self, run_id: str, sequence: int) -> Optional[Dict[str, Any]]:
        """Reconstruct state at a specific event sequence.

        Args:
            run_id: The run ID
            sequence: The event sequence number

        Returns:
            The reconstructed state at that point
        """
        run = self.get_run(run_id)
        if run:
            reducer = StateReducer()
            return reducer.reduce_to_event(run, sequence)
        return None

    def replay(self, run_id: str) -> Optional[ReplayResult]:
        """Replay a run and produce a result.

        Args:
            run_id: The run ID to replay

        Returns:
            A ReplayResult with reconstruction data
        """
        run = self.get_run(run_id)
        if not run:
            return None

        # Reconstruct state
        final_state = self.reconstruct_state(run_id)

        # Build timeline
        timeline = self.get_timeline(run_id)
        timeline_entries = timeline.all() if timeline else []

        # Build execution tree
        execution_tree = self._build_execution_tree(run)

        # Run consistency check
        from argus.replay.consistency import check_consistency
        consistency_issues = check_consistency(run)

        return ReplayResult(
            run_id=run_id,
            status=run.status,
            timeline=timeline_entries,
            execution_tree=execution_tree,
            final_state=final_state,
            consistency_issues=consistency_issues,
            event_count=len(run.events),
            duration=run.duration,
        )

    def _build_execution_tree(self, run: ReplayRun) -> Optional[Dict[str, Any]]:
        """Build the execution tree for a run."""
        from argus.replay.tree import build_execution_tree
        return build_execution_tree(run)
