"""Subagent manager for ARGUS."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.subagents.models import (
    Subagent,
    SubagentId,
    SubagentResult,
    SubagentRole,
    SubagentStatus,
    SubagentTask,
    is_valid_transition,
)


class SubagentManager:
    """Manages subagent lifecycle."""

    def __init__(self):
        self._subagents: Dict[str, Subagent] = {}
        self._event_handlers: List[Callable] = []

    @property
    def count(self) -> int:
        return len(self._subagents)

    def add_event_handler(self, handler: Callable) -> None:
        """Add an event handler for lifecycle events."""
        self._event_handlers.append(handler)

    def _emit_event(self, event_type: str, subagent: Subagent, **kwargs) -> None:
        """Emit a lifecycle event."""
        for handler in self._event_handlers:
            try:
                handler(event_type, subagent, **kwargs)
            except Exception:
                pass

    def create(
        self,
        task: SubagentTask,
        parent_id: Optional[str] = None,
    ) -> Subagent:
        """Create a new subagent."""
        subagent = Subagent(
            parent_run_id=task.parent_run_id,
            parent_task_id=task.parent_task_id,
            role=task.role,
            objective=task.objective,
            status=SubagentStatus.CREATED,
            budget=task.budget,
            parent_id=parent_id,
        )

        self._subagents[str(subagent.id)] = subagent
        self._emit_event("subagent.created", subagent)

        return subagent

    def get(self, subagent_id: str) -> Optional[Subagent]:
        """Get a subagent by ID."""
        return self._subagents.get(subagent_id)

    def list(self) -> List[Subagent]:
        """List all subagents."""
        return list(self._subagents.values())

    def list_by_parent(self, parent_id: str) -> List[Subagent]:
        """List subagents by parent ID."""
        return [s for s in self._subagents.values() if s.parent_id == parent_id]

    def list_by_status(self, status: SubagentStatus) -> List[Subagent]:
        """List subagents by status."""
        return [s for s in self._subagents.values() if s.status == status]

    def list_active(self) -> List[Subagent]:
        """List active subagents."""
        return [s for s in self._subagents.values() if s.is_active]

    def list_by_run(self, run_id: str) -> List[Subagent]:
        """List subagents by parent run ID."""
        return [s for s in self._subagents.values() if s.parent_run_id == run_id]

    def _transition(self, subagent: Subagent, new_status: SubagentStatus) -> bool:
        """Transition a subagent to a new status."""
        if not is_valid_transition(subagent.status, new_status):
            return False

        old_status = subagent.status
        subagent.status = new_status

        # Update timestamps
        if new_status == SubagentStatus.RUNNING and subagent.started_at is None:
            subagent.started_at = time.time()
        if new_status in (
            SubagentStatus.COMPLETED,
            SubagentStatus.FAILED,
            SubagentStatus.CANCELLED,
            SubagentStatus.TIMED_OUT,
            SubagentStatus.BLOCKED,
        ):
            subagent.completed_at = time.time()

        self._emit_event(
            f"subagent.{new_status.value}",
            subagent,
            old_status=old_status,
        )

        return True

    def start(self, subagent_id: str) -> bool:
        """Start a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        # Auto-transition from CREATED to QUEUED first if needed
        if subagent.status == SubagentStatus.CREATED:
            if not self._transition(subagent, SubagentStatus.QUEUED):
                return False
        return self._transition(subagent, SubagentStatus.RUNNING)

    def pause(self, subagent_id: str) -> bool:
        """Pause a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        return self._transition(subagent, SubagentStatus.PAUSED)

    def resume(self, subagent_id: str) -> bool:
        """Resume a paused subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        return self._transition(subagent, SubagentStatus.RUNNING)

    def complete(self, subagent_id: str, result: Optional[SubagentResult] = None) -> bool:
        """Complete a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        if result:
            subagent.result = result.to_dict()
        return self._transition(subagent, SubagentStatus.COMPLETED)

    def fail(self, subagent_id: str, error: str = "") -> bool:
        """Fail a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        subagent.error = error
        return self._transition(subagent, SubagentStatus.FAILED)

    def cancel(self, subagent_id: str) -> bool:
        """Cancel a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        return self._transition(subagent, SubagentStatus.CANCELLED)

    def timeout(self, subagent_id: str) -> bool:
        """Mark a subagent as timed out."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        return self._transition(subagent, SubagentStatus.TIMED_OUT)

    def block(self, subagent_id: str, reason: str = "") -> bool:
        """Block a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        subagent.error = reason
        return self._transition(subagent, SubagentStatus.BLOCKED)

    def update_budget(self, subagent_id: str, budget_updates: Dict[str, int]) -> bool:
        """Update budget usage for a subagent."""
        subagent = self._subagents.get(subagent_id)
        if not subagent:
            return False
        for key, value in budget_updates.items():
            subagent.budget_used[key] = subagent.budget_used.get(key, 0) + value
        return True

    def add_child(self, parent_id: str, child_id: str) -> bool:
        """Add a child to a parent subagent."""
        parent = self._subagents.get(parent_id)
        if not parent:
            return False
        if child_id not in parent.child_ids:
            parent.child_ids.append(child_id)
        return True

    def remove(self, subagent_id: str) -> bool:
        """Remove a subagent."""
        if subagent_id in self._subagents:
            del self._subagents[subagent_id]
            return True
        return False

    def clear(self) -> None:
        """Remove all subagents."""
        self._subagents.clear()

    def get_tree(self, parent_id: str) -> Dict[str, Any]:
        """Get subagent tree for a parent."""
        parent = self._subagents.get(parent_id)
        if not parent:
            return {}

        return {
            "id": str(parent.id),
            "role": parent.role.value,
            "status": parent.status.value,
            "objective": parent.objective,
            "children": [
                self.get_tree(child_id) for child_id in parent.child_ids
                if child_id in self._subagents
            ],
        }

    def summary(self) -> Dict[str, Any]:
        """Get summary of all subagents."""
        by_status: Dict[str, int] = {}
        for subagent in self._subagents.values():
            status = subagent.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total": len(self._subagents),
            "active": len(self.list_active()),
            "by_status": by_status,
        }
