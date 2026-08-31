"""ARGUS Replay checkpoint system."""

import copy
import logging
from typing import Any, Dict, List, Optional

from argus.replay.models import (
    ReplayCheckpoint,
    ReplayRun,
)

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages state checkpoints for replay.

    Uses existing SnapshotManager where possible.
    """

    def __init__(self, run: ReplayRun):
        self._run = run

    def get_checkpoints(self) -> List[ReplayCheckpoint]:
        """Get all checkpoints for the run."""
        return sorted(self._run.checkpoints, key=lambda c: c.sequence)

    def get_checkpoint(self, checkpoint_id: str) -> Optional[ReplayCheckpoint]:
        """Get a specific checkpoint by ID."""
        for checkpoint in self._run.checkpoints:
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint
        return None

    def get_checkpoint_at_sequence(self, sequence: int) -> Optional[ReplayCheckpoint]:
        """Get the checkpoint closest to but not after the given sequence."""
        best = None
        for checkpoint in self._run.checkpoints:
            if checkpoint.sequence <= sequence:
                if best is None or checkpoint.sequence > best.sequence:
                    best = checkpoint
        return best

    def get_state_at_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get the state at a specific checkpoint."""
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint:
            return copy.deepcopy(checkpoint.state)
        return None

    def compare_checkpoints(self, id1: str, id2: str) -> Dict[str, Any]:
        """Compare two checkpoints and return differences."""
        cp1 = self.get_checkpoint(id1)
        cp2 = self.get_checkpoint(id2)

        if not cp1 or not cp2:
            return {"error": "One or both checkpoints not found"}

        state1 = cp1.state
        state2 = cp2.state

        all_keys = set(state1.keys()) | set(state2.keys())

        differences = {}
        for key in all_keys:
            val1 = state1.get(key)
            val2 = state2.get(key)
            if val1 != val2:
                differences[key] = {
                    "before": val1,
                    "after": val2,
                }

        return {
            "checkpoint1": id1,
            "checkpoint2": id2,
            "differences": differences,
            "keys_added": list(set(state2.keys()) - set(state1.keys())),
            "keys_removed": list(set(state1.keys()) - set(state2.keys())),
        }

    def restore_for_analysis(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Restore state at a checkpoint for analysis.

        This returns a copy of the state for read-only analysis.
        It does NOT modify any production state.
        """
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint:
            return copy.deepcopy(checkpoint.state)
        return None

    def list_checkpoint_labels(self) -> List[Dict[str, Any]]:
        """List all checkpoints with their labels."""
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "sequence": cp.sequence,
                "timestamp": cp.timestamp,
                "label": cp.label,
            }
            for cp in self.get_checkpoints()
        ]
