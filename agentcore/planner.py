from typing import Any, Optional
from dataclasses import dataclass, field

from .task import PlanStep


class Planner:
    def __init__(self):
        self._templates = {
            "bug_fix": [
                PlanStep(action="inspect", description="Understand the bug by examining relevant code"),
                PlanStep(action="reproduce", description="Create or find a reproduction case"),
                PlanStep(action="hypothesize", description="Form a hypothesis about the root cause"),
                PlanStep(action="validate", description="Verify the hypothesis with experiments"),
                PlanStep(action="implement", description="Implement the fix"),
                PlanStep(action="test", description="Run tests to verify the fix"),
                PlanStep(action="verify", description="Ensure no regressions"),
            ],
            "feature_implement": [
                PlanStep(action="analyze", description="Analyze requirements and design approach"),
                PlanStep(action="design", description="Design the implementation approach"),
                PlanStep(action="implement", description="Implement the feature"),
                PlanStep(action="test", description="Add tests for the feature"),
                PlanStep(action="verify", description="Verify the implementation"),
            ],
            "refactor": [
                PlanStep(action="understand", description="Understand the existing code structure"),
                PlanStep(action="identify", description="Identify areas for improvement"),
                PlanStep(action="refactor", description="Perform the refactoring"),
                PlanStep(action="verify", description="Verify behavior is unchanged"),
            ],
            "investigate": [
                PlanStep(action="explore", description="Explore the codebase"),
                PlanStep(action="analyze", description="Analyze relevant files and patterns"),
                PlanStep(action="summarize", description="Summarize findings"),
            ],
        }

    def plan(self, task_type: str, user_request: str, context: dict[str, Any] | None = None) -> list[PlanStep]:
        if task_type in self._templates:
            return list(self._templates[task_type])

        return [
            PlanStep(action="understand", description="Understand the user request"),
            PlanStep(action="explore", description="Explore relevant project files"),
            PlanStep(action="decide", description="Decide on the approach"),
            PlanStep(action="implement", description="Implement the solution"),
            PlanStep(action="verify", description="Verify the solution"),
        ]

    def adapt_plan(self, original_plan: list[PlanStep], discoveries: list[str]) -> list[PlanStep]:
        adapted = list(original_plan)
        return adapted

    def suggest_next_step(self, plan: list[PlanStep], completed: list[str]) -> Optional[PlanStep]:
        for step in plan:
            if step.action not in completed:
                return step
        return None