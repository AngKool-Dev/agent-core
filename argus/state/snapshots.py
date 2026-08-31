"""State snapshots - point-in-time state capture."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.state.models import AgentState


@dataclass
class StateSnapshot:
    """A point-in-time snapshot of agent state."""
    run_id: str
    timestamp: float = field(default_factory=time.time)
    state: Dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "state": self.state,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSnapshot":
        return cls(
            run_id=data.get("run_id", ""),
            timestamp=data.get("timestamp", time.time()),
            state=data.get("state", {}),
            label=data.get("label", ""),
        )

    @classmethod
    def capture(cls, state: AgentState, label: str = "") -> "StateSnapshot":
        """Capture a snapshot of the current state."""
        return cls(
            run_id=state.run_id,
            timestamp=time.time(),
            state=state.to_dict(),
            label=label,
        )


class SnapshotManager:
    """Manages state snapshots."""

    def __init__(self, max_snapshots_per_run: int = 10):
        self._snapshots: Dict[str, List[StateSnapshot]] = {}
        self._max_per_run = max_snapshots_per_run

    def capture(self, state: AgentState, label: str = "") -> StateSnapshot:
        """Capture a snapshot."""
        snapshot = StateSnapshot.capture(state, label)

        if state.run_id not in self._snapshots:
            self._snapshots[state.run_id] = []

        self._snapshots[state.run_id].append(snapshot)

        # Trim if needed
        if len(self._snapshots[state.run_id]) > self._max_per_run:
            self._snapshots[state.run_id] = self._snapshots[state.run_id][-self._max_per_run:]

        return snapshot

    def get_snapshots(self, run_id: str) -> List[StateSnapshot]:
        """Get all snapshots for a run."""
        return self._snapshots.get(run_id, [])

    def get_last_snapshot(self, run_id: str) -> Optional[StateSnapshot]:
        """Get the last snapshot for a run."""
        snapshots = self._snapshots.get(run_id, [])
        return snapshots[-1] if snapshots else None

    def get_snapshot_before(self, run_id: str, timestamp: float) -> Optional[StateSnapshot]:
        """Get the last snapshot before a timestamp."""
        snapshots = self._snapshots.get(run_id, [])
        result = None
        for snapshot in snapshots:
            if snapshot.timestamp < timestamp:
                result = snapshot
            else:
                break
        return result

    def clear(self, run_id: str) -> None:
        """Clear snapshots for a run."""
        self._snapshots.pop(run_id, None)

    def clear_all(self) -> None:
        """Clear all snapshots."""
        self._snapshots.clear()