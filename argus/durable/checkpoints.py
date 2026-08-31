"""ARGUS Durable Execution Checkpoints.

Integrates with existing SnapshotManager and StateStore.
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

from argus.durable.models import (
    Checkpoint,
    CheckpointPhase,
    generate_checkpoint_id,
)

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = os.path.join(os.path.expanduser("~"), ".argus", "checkpoints")


class CheckpointManager:
    """Manages execution checkpoints.

    Integrates with existing SnapshotManager and StateStore.
    Does not create a second persistent state database.
    """

    def __init__(self, checkpoint_dir: str = CHECKPOINT_DIR):
        self._checkpoint_dir = checkpoint_dir
        os.makedirs(self._checkpoint_dir, exist_ok=True)

    def create_checkpoint(
        self,
        run_id: str,
        phase: CheckpointPhase,
        state_snapshot: Dict[str, Any],
        operation_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Checkpoint:
        """Create a checkpoint."""
        checkpoint = Checkpoint(
            checkpoint_id=generate_checkpoint_id(),
            run_id=run_id,
            phase=phase,
            state_snapshot=state_snapshot,
            operation_id=operation_id,
            metadata=metadata or {},
        )
        checkpoint.integrity_hash = self._compute_integrity_hash(checkpoint)
        self._save_checkpoint(checkpoint)
        logger.debug(f"Created checkpoint {checkpoint.checkpoint_id} for phase {phase.value}")
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get a checkpoint by ID."""
        path = self._checkpoint_path(checkpoint_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            checkpoint = Checkpoint.from_dict(data)
            if not self._verify_integrity(checkpoint):
                logger.error(f"Checkpoint {checkpoint_id} integrity check failed")
                return None
            return checkpoint
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def get_latest_checkpoint(self, run_id: str) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a run."""
        checkpoints = self.get_checkpoints(run_id)
        if not checkpoints:
            return None
        return max(checkpoints, key=lambda c: c.timestamp)

    def get_checkpoints(self, run_id: str) -> List[Checkpoint]:
        """Get all checkpoints for a run."""
        checkpoints = []
        prefix = f"{run_id}_"
        for filename in os.listdir(self._checkpoint_dir):
            if filename.startswith(prefix) and filename.endswith(".json"):
                checkpoint_id = filename[:-5]  # Remove .json
                checkpoint = self.get_checkpoint(checkpoint_id)
                if checkpoint:
                    checkpoints.append(checkpoint)
        return sorted(checkpoints, key=lambda c: c.timestamp)

    def get_checkpoint_before_operation(
        self, run_id: str, operation_id: str
    ) -> Optional[Checkpoint]:
        """Get the latest checkpoint before a specific operation."""
        checkpoints = self.get_checkpoints(reversed([c for c in self.get_checkpoints(run_id) if c.operation_id == operation_id]))
        all_checkpoints = self.get_checkpoints(run_id)
        relevant = [c for c in all_checkpoints if c.operation_id != operation_id]
        if not relevant:
            return None
        return relevant[-1] if relevant else None

    def create_state_snapshot(
        self,
        run_id: str,
        agent_state: Any = None,
        additional_state: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a state snapshot from existing state infrastructure."""
        snapshot = {
            "run_id": run_id,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }

        if agent_state:
            if hasattr(agent_state, "to_dict"):
                snapshot["agent_state"] = agent_state.to_dict()
            elif isinstance(agent_state, dict):
                snapshot["agent_state"] = agent_state
            else:
                snapshot["agent_state"] = {"repr": str(agent_state)}

        if additional_state:
            snapshot.update(additional_state)

        return snapshot

    def restore_state_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Restore state from a snapshot."""
        return snapshot.get("agent_state", {})

    def _compute_integrity_hash(self, checkpoint: Checkpoint) -> str:
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

    def _verify_integrity(self, checkpoint: Checkpoint) -> bool:
        """Verify the integrity of a checkpoint."""
        if not checkpoint.integrity_hash:
            return False
        expected = self._compute_integrity_hash(checkpoint)
        return checkpoint.integrity_hash == expected

    def _save_checkpoint(self, checkpoint: Checkpoint):
        """Save checkpoint to disk."""
        path = self._checkpoint_path(checkpoint.checkpoint_id)
        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

    def _checkpoint_path(self, checkpoint_id: str) -> str:
        """Get the file path for a checkpoint."""
        return os.path.join(self._checkpoint_dir, f"{checkpoint_id}.json")

    def delete_checkpoints(self, run_id: str):
        """Delete all checkpoints for a run."""
        for checkpoint in self.get_checkpoints(run_id):
            path = self._checkpoint_path(checkpoint.checkpoint_id)
            if os.path.exists(path):
                os.remove(path)
