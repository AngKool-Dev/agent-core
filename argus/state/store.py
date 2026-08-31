"""State store - persists AgentState using existing memory system."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from argus.state.models import AgentState, RunStatus


STATE_TYPE = "argus_state"
STATE_PREFIX = "ARGUS_STATE:"


class StateStore:
    """Stores agent state using the existing memory system."""

    def __init__(self, memory_manager=None, project_path: Optional[str] = None):
        self._memory = memory_manager
        self._project_path = project_path

    def set_project(self, project_path: str) -> None:
        self._project_path = project_path

    def save_state(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Save agent state to memory."""
        if not self._memory or not self._project_path:
            return None

        try:
            content = json.dumps(state.to_dict(), default=str)
            result = self._memory.store(
                type=STATE_TYPE,
                content=f"{STATE_PREFIX}{state.run_id}\n{content}",
                project=self._project_path,
                importance=0.9,
            )
            return result
        except Exception:
            return None

    def load_state(self, run_id: str) -> Optional[AgentState]:
        """Load agent state from memory."""
        if not self._memory or not self._project_path:
            return None

        try:
            results = self._memory.search(
                f"{STATE_PREFIX}{run_id}",
                project=self._project_path,
                limit=1,
            )
            if results:
                content = results[0].get("content", "")
                # Remove prefix
                if content.startswith(f"{STATE_PREFIX}{run_id}\n"):
                    content = content[len(f"{STATE_PREFIX}{run_id}\n"):]
                data = json.loads(content)
                return AgentState.from_dict(data)
        except Exception:
            pass
        return None

    def list_states(self, status: Optional[RunStatus] = None, limit: int = 20) -> List[AgentState]:
        """List agent states."""
        if not self._memory or not self._project_path:
            return []

        try:
            results = self._memory.search(
                STATE_PREFIX,
                project=self._project_path,
                limit=limit,
            )
            states = []
            for result in results:
                content = result.get("content", "")
                if f"{STATE_PREFIX}" in content:
                    # Extract JSON after prefix line
                    lines = content.split("\n", 1)
                    if len(lines) == 2:
                        try:
                            data = json.loads(lines[1])
                            state = AgentState.from_dict(data)
                            if status is None or state.status == status:
                                states.append(state)
                        except Exception:
                            continue
            return states
        except Exception:
            return []

    def get_latest_state(self) -> Optional[AgentState]:
        """Get the most recent state."""
        states = self.list_states(limit=1)
        return states[0] if states else None

    def get_latest_running(self) -> Optional[AgentState]:
        """Get the most recent running state."""
        states = self.list_states(status=RunStatus.RUNNING, limit=1)
        if not states:
            states = self.list_states(status=RunStatus.PAUSED, limit=1)
        return states[0] if states else None

    def delete_state(self, run_id: str) -> bool:
        """Delete a state."""
        if not self._memory or not self._project_path:
            return False

        try:
            results = self._memory.search(
                f"{STATE_PREFIX}{run_id}",
                project=self._project_path,
                limit=1,
            )
            if results:
                memory_id = results[0].get("id")
                if memory_id:
                    self._memory.update(memory_id, "")
                    return True
        except Exception:
            pass
        return False

    def update_state(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Update an existing state."""
        return self.save_state(state)