"""Subagent orchestrator for ARGUS."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.subagents.budget import SubagentBudget, create_budget, derive_child_budget
from argus.subagents.delegation import DelegationContract, create_contract
from argus.subagents.executor import SubagentExecutor
from argus.subagents.manager import SubagentManager
from argus.subagents.models import (
    Subagent,
    SubagentId,
    SubagentResult,
    SubagentRole,
    SubagentStatus,
    SubagentTask,
)


class SubagentOrchestrator:
    """Orchestrates subagent delegation."""

    def __init__(
        self,
        manager: Optional[SubagentManager] = None,
        max_concurrent: int = 3,
    ):
        self._manager = manager or SubagentManager()
        self._max_concurrent = max_concurrent
        self._event_handlers: List[Callable] = []

    @property
    def manager(self) -> SubagentManager:
        return self._manager

    def add_event_handler(self, handler: Callable) -> None:
        """Add an event handler."""
        self._event_handlers.append(handler)

    def _emit_event(self, event_type: str, **kwargs) -> None:
        """Emit an event."""
        for handler in self._event_handlers:
            try:
                handler(event_type, **kwargs)
            except Exception:
                pass

    def delegate(
        self,
        objective: str,
        role: SubagentRole,
        parent_run_id: str = "",
        parent_task_id: str = "",
        inputs: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        budget_overrides: Optional[Dict[str, int]] = None,
        parent_id: Optional[str] = None,
    ) -> Subagent:
        """Delegate a task to a new subagent."""
        # Create task
        task = SubagentTask(
            parent_run_id=parent_run_id,
            parent_task_id=parent_task_id,
            objective=objective,
            role=role,
            inputs=inputs or {},
            constraints=constraints or {},
            budget=budget_overrides or {},
        )

        # Create subagent
        subagent = self._manager.create(task, parent_id=parent_id)

        # Update parent's child list
        if parent_id:
            self._manager.add_child(parent_id, str(subagent.id))

        self._emit_event(
            "subagent.delegated",
            subagent_id=str(subagent.id),
            role=role.value,
            objective=objective,
        )

        return subagent

    def start(self, subagent_id: str) -> bool:
        """Start a subagent."""
        return self._manager.start(subagent_id)

    def execute(self, subagent_id: str) -> Optional[SubagentResult]:
        """Execute a subagent."""
        subagent = self._manager.get(subagent_id)
        if not subagent:
            return None

        # Create task from subagent
        task = SubagentTask(
            parent_run_id=subagent.parent_run_id,
            parent_task_id=subagent.parent_task_id,
            objective=subagent.objective,
            role=subagent.role,
            budget=subagent.budget,
        )

        # Create budget
        budget = create_budget(subagent.role, subagent.budget)

        # Create executor
        executor = SubagentExecutor(budget=budget)
        for handler in self._event_handlers:
            executor.add_event_handler(handler)

        # Execute
        if self._manager.start(subagent_id):
            result = executor.execute(subagent, task)

            # Update subagent with result
            if result.status == SubagentStatus.COMPLETED:
                self._manager.complete(subagent_id, result)
            elif result.status == SubagentStatus.TIMED_OUT:
                self._manager.timeout(subagent_id)
            else:
                self._manager.fail(subagent_id, result.summary)

            return result

        return None

    def cancel(self, subagent_id: str) -> bool:
        """Cancel a subagent."""
        return self._manager.cancel(subagent_id)

    def pause(self, subagent_id: str) -> bool:
        """Pause a subagent."""
        return self._manager.pause(subagent_id)

    def resume(self, subagent_id: str) -> bool:
        """Resume a subagent."""
        return self._manager.resume(subagent_id)

    def get(self, subagent_id: str) -> Optional[Subagent]:
        """Get a subagent."""
        return self._manager.get(subagent_id)

    def list_active(self) -> List[Subagent]:
        """List active subagents."""
        return self._manager.list_active()

    def list_by_run(self, run_id: str) -> List[Subagent]:
        """List subagents by run ID."""
        return self._manager.list_by_run(run_id)

    def get_tree(self, parent_id: str) -> Dict[str, Any]:
        """Get subagent tree."""
        return self._manager.get_tree(parent_id)

    def can_execute(self) -> bool:
        """Check if we can execute more subagents."""
        return len(self.list_active()) < self._max_concurrent

    def summary(self) -> Dict[str, Any]:
        """Get orchestrator summary."""
        return {
            "max_concurrent": self._max_concurrent,
            "active": len(self.list_active()),
            **self._manager.summary(),
        }


def create_orchestrator(max_concurrent: int = 3) -> SubagentOrchestrator:
    """Create a subagent orchestrator."""
    return SubagentOrchestrator(max_concurrent=max_concurrent)
