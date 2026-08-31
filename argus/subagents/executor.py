"""Subagent executor for ARGUS."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.subagents.budget import SubagentBudget, create_budget
from argus.subagents.models import (
    Subagent,
    SubagentResult,
    SubagentRole,
    SubagentStatus,
    SubagentTask,
)


class SubagentExecutor:
    """Executes a subagent task through the existing ARGUS loop."""

    def __init__(self, budget: Optional[SubagentBudget] = None):
        self._budget = budget
        self._event_handlers: List[Callable] = []

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

    def execute(
        self,
        subagent: Subagent,
        task: SubagentTask,
    ) -> SubagentResult:
        """Execute a subagent task."""
        start_time = time.time()

        # Create budget if not provided
        if not self._budget:
            self._budget = create_budget(task.role, task.budget)

        # Update subagent budget
        subagent.budget = self._budget.to_dict()

        self._emit_event(
            "subagent.started",
            subagent_id=str(subagent.id),
            task_id=task.task_id,
        )

        try:
            # Execute the task (simplified - in real implementation, this would
            # integrate with the existing adaptive loop)
            result = self._run_task(subagent, task)

            # Update budget usage
            subagent.budget_used = {
                "model_calls": self._budget.model_calls,
                "tool_calls": self._budget.tool_calls,
                "iterations": self._budget.iterations,
            }

            self._emit_event(
                "subagent.completed",
                subagent_id=str(subagent.id),
                task_id=task.task_id,
            )

            return result

        except TimeoutError:
            self._emit_event(
                "subagent.timeout",
                subagent_id=str(subagent.id),
                task_id=task.task_id,
            )
            return SubagentResult(
                task_id=task.task_id,
                subagent_id=str(subagent.id),
                status=SubagentStatus.TIMED_OUT,
                summary="Subagent timed out",
                errors=["Budget/time exhausted"],
                duration=time.time() - start_time,
            )

        except Exception as e:
            self._emit_event(
                "subagent.failed",
                subagent_id=str(subagent.id),
                task_id=task.task_id,
                error=str(e),
            )
            return SubagentResult(
                task_id=task.task_id,
                subagent_id=str(subagent.id),
                status=SubagentStatus.FAILED,
                summary=f"Subagent failed: {str(e)}",
                errors=[str(e)],
                duration=time.time() - start_time,
            )

    def _run_task(
        self,
        subagent: Subagent,
        task: SubagentTask,
    ) -> SubagentResult:
        """Run the actual task (bounded by budget)."""
        start_time = time.time()
        findings = []
        artifacts = []
        errors = []

        # Iterate within budget
        while not self._budget.is_exhausted:
            if not self._budget.consume_iteration():
                break

            # Simulate work being done
            # In real implementation, this would:
            # 1. Build context from ContextEngine
            # 2. Call model through ModelRouter
            # 3. Execute capabilities through CapabilityRouter + SecurityKernel
            # 4. Verify through VerificationEngine
            # 5. Recover through RecoveryEngine if needed

            # Check termination conditions
            if self._should_terminate(task):
                break

        # Build result
        if self._budget.is_exhausted:
            status = SubagentStatus.TIMED_OUT
            summary = f"Budget exhausted: {self._budget.exhausted_reason}"
        else:
            status = SubagentStatus.COMPLETED
            summary = f"Task completed: {task.objective}"

        return SubagentResult(
            task_id=task.task_id,
            subagent_id=str(subagent.id),
            status=status,
            summary=summary,
            findings=findings,
            artifacts=artifacts,
            errors=errors,
            duration=time.time() - start_time,
            budget_usage=self._budget.usage_summary(),
        )

    def _should_terminate(self, task: SubagentTask) -> bool:
        """Check if the task should terminate."""
        # Check deadline
        if task.deadline and time.time() > task.deadline:
            return True

        # Check custom termination conditions
        conditions = task.constraints.get("termination_conditions", [])
        for condition in conditions:
            if condition == "first_result":
                return True

        return False
