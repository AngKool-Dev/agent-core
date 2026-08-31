"""Recovery planner - generates recovery plans based on failure analysis."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.recovery.result import FailureClass, FailureEvidence, RecoveryStrategyType
from argus.recovery.state import RecoveryState


@dataclass
class RecoveryPlan:
    """A plan for recovery."""
    strategy: RecoveryStrategyType
    description: str
    steps: List[str]
    new_assumptions: Dict[str, bool] = field(default_factory=dict)
    invalidated_assumptions: List[str] = field(default_factory=list)
    capability_id: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "description": self.description,
            "steps": self.steps,
            "capability_id": self.capability_id,
        }


class RecoveryPlanner:
    """Generates recovery plans based on failure analysis."""

    def create_recovery_plan(
        self,
        failure: FailureEvidence,
        state: RecoveryState,
        available_capabilities: List[str] = None,
    ) -> RecoveryPlan:
        """Create a recovery plan based on failure and state."""
        strategy = self._select_strategy(failure, state)

        if strategy == RecoveryStrategyType.RETRY:
            return self._plan_retry(failure, state)
        elif strategy == RecoveryStrategyType.FALLBACK:
            return self._plan_fallback(failure, state, available_capabilities or [])
        elif strategy == RecoveryStrategyType.REPLAN:
            return self._plan_replan(failure, state)
        elif strategy == RecoveryStrategyType.REPAIR:
            return self._plan_repair(failure, state)
        elif strategy == RecoveryStrategyType.BACKEND_SWITCH:
            return self._plan_backend_switch(failure, state, available_capabilities or [])
        elif strategy == RecoveryStrategyType.ESCALATE:
            return self._plan_escalate(failure, state)
        else:
            return self._plan_retry(failure, state)

    def _select_strategy(
        self,
        failure: FailureEvidence,
        state: RecoveryState,
    ) -> RecoveryStrategyType:
        """Select the best recovery strategy."""
        from argus.recovery.strategy import RecoveryStrategies
        from argus.recovery.budget import RecoveryBudget

        # Create a budget based on state
        budget = RecoveryBudget(
            max_attempts=10 - state.attempt_count,
            max_retries=3,
            max_replans=3 - len([a for a in state.recovery_actions if a.strategy == RecoveryStrategyType.REPLAN]),
            max_backend_switches=2,
            max_repair_cycles=4,
        )

        return RecoveryStrategies.select_best_strategy(failure.failure_class, budget) or RecoveryStrategyType.RETRY

    def _plan_retry(self, failure: FailureEvidence, state: RecoveryState) -> RecoveryPlan:
        """Plan a retry."""
        last_attempt = state.last_attempt
        return RecoveryPlan(
            strategy=RecoveryStrategyType.RETRY,
            description=f"Retry the failed operation: {failure.message[:100]}",
            steps=[
                "Wait briefly before retrying",
                "Retry the same operation",
                "Verify the result",
            ],
            capability_id=last_attempt.capability_id if last_attempt else "",
            input_data=last_attempt.input_data if last_attempt else {},
        )

    def _plan_fallback(
        self,
        failure: FailureEvidence,
        state: RecoveryState,
        available_capabilities: List[str],
    ) -> RecoveryPlan:
        """Plan a fallback to an alternative capability."""
        last_attempt = state.last_attempt
        # Find a fallback capability
        fallback_id = self._find_fallback(last_attempt.capability_id if last_attempt else "", available_capabilities)

        return RecoveryPlan(
            strategy=RecoveryStrategyType.FALLBACK,
            description=f"Fallback to alternative capability: {fallback_id}",
            steps=[
                f"Switch to fallback capability: {fallback_id}",
                "Execute with fallback",
                "Verify the result",
            ],
            capability_id=fallback_id,
            input_data=last_attempt.input_data if last_attempt else {},
        )

    def _plan_replan(self, failure: FailureEvidence, state: RecoveryState) -> RecoveryPlan:
        """Plan a replan."""
        # Identify what went wrong
        invalid_assumptions = state.get_changed_assumptions()
        learned_facts = state.learned_facts

        steps = [
            "Analyze failure evidence",
            "Identify invalidated assumptions",
        ]
        if invalid_assumptions:
            steps.append(f"Invalid assumptions: {', '.join(invalid_assumptions)}")
        if learned_facts:
            steps.append(f"Learned: {', '.join(learned_facts[-3:])}")
        steps.extend([
            "Generate new approach",
            "Execute new plan",
            "Verify the result",
        ])

        return RecoveryPlan(
            strategy=RecoveryStrategyType.REPLAN,
            description=f"Replan based on failure analysis: {failure.message[:100]}",
            steps=steps,
            invalidated_assumptions=invalid_assumptions,
        )

    def _plan_repair(self, failure: FailureEvidence, state: RecoveryState) -> RecoveryPlan:
        """Plan a repair."""
        steps = [
            "Analyze the failure",
        ]

        if failure.failure_class == FailureClass.CODE:
            steps.extend([
                "Identify the code issue",
                "Apply fix",
                "Re-run tests",
            ])
        elif failure.failure_class == FailureClass.EXECUTION:
            steps.extend([
                "Check dependencies",
                "Fix environment",
                "Retry execution",
            ])
        elif failure.failure_class == FailureClass.ENVIRONMENT:
            steps.extend([
                "Identify environment issue",
                "Fix environment",
                "Retry operation",
            ])
        else:
            steps.extend([
                "Identify the issue",
                "Apply fix",
                "Retry",
            ])

        return RecoveryPlan(
            strategy=RecoveryStrategyType.REPAIR,
            description=f"Repair based on failure: {failure.message[:100]}",
            steps=steps,
        )

    def _plan_backend_switch(
        self,
        failure: FailureEvidence,
        state: RecoveryState,
        available_capabilities: List[str],
    ) -> RecoveryPlan:
        """Plan a backend switch."""
        last_attempt = state.last_attempt
        current_backend = last_attempt.capability_id if last_attempt else ""
        new_backend = self._find_fallback(current_backend, available_capabilities)

        return RecoveryPlan(
            strategy=RecoveryStrategyType.BACKEND_SWITCH,
            description=f"Switch backend from {current_backend} to {new_backend}",
            steps=[
                f"Current backend failed: {current_backend}",
                f"Switch to alternative: {new_backend}",
                "Execute with new backend",
                "Verify the result",
            ],
            capability_id=new_backend,
            input_data=last_attempt.input_data if last_attempt else {},
        )

    def _plan_escalate(self, failure: FailureEvidence, state: RecoveryState) -> RecoveryPlan:
        """Plan an escalation to user."""
        return RecoveryPlan(
            strategy=RecoveryStrategyType.ESCALATE,
            description=f"Escalate to user: {failure.message[:100]}",
            steps=[
                "Recovery budget exhausted or user input required",
                f"Failure: {failure.message}",
                "Present options to user",
                "Wait for user decision",
            ],
        )

    def _find_fallback(self, current_capability: str, available: List[str]) -> str:
        """Find a fallback capability."""
        # Simple strategy: find first available capability that's not the current one
        for cap in available:
            if cap != current_capability:
                return cap
        return available[0] if available else current_capability