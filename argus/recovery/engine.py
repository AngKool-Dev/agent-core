"""Recovery engine - orchestrates intelligent failure recovery."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.recovery.budget import RecoveryBudget
from argus.recovery.classifier import FailureClassifier
from argus.recovery.planner import RecoveryPlanner, RecoveryPlan
from argus.recovery.result import (
    FailureClass,
    FailureEvidence,
    RecoveryAction,
    RecoveryResult,
    RecoveryStatus,
    RecoveryStrategyType,
)
from argus.recovery.state import AttemptRecord, RecoveryState
from argus.recovery.strategy import RecoveryStrategies


class RecoveryEngine:
    """Engine for intelligent failure recovery."""

    def __init__(
        self,
        budget: Optional[RecoveryBudget] = None,
        classifier: Optional[FailureClassifier] = None,
        planner: Optional[RecoveryPlanner] = None,
        max_recovery_cycles: int = 5,
    ):
        self._budget = budget or RecoveryBudget.default()
        self._classifier = classifier or FailureClassifier()
        self._planner = planner or RecoveryPlanner()
        self._max_recovery_cycles = max_recovery_cycles

    def recover(
        self,
        failure_message: str,
        task: str,
        state: Optional[RecoveryState] = None,
        execute_fn: Optional[Callable] = None,
        available_capabilities: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> RecoveryResult:
        """Attempt to recover from a failure."""
        start = time.time()
        context = context or {}

        # Initialize state if not provided
        if state is None:
            state = RecoveryState(task=task)

        # Classify the failure
        evidence = self._classifier.classify(
            message=failure_message,
            command=context.get("command", ""),
            return_code=context.get("return_code", 0),
            context=context,
        )
        state.add_failure(evidence)

        # Create recovery result
        result = RecoveryResult(
            status=RecoveryStatus.FAILED,
            original_failure=evidence,
        )

        # Check budget
        if self._budget.exhausted:
            result.status = RecoveryStatus.EXHAUSTED
            result.message = f"Recovery budget exhausted: {self._budget.summary()}"
            result.budget_remaining = self._budget.to_dict()
            result.duration = time.time() - start
            return result

        # Get recovery strategies
        strategies = RecoveryStrategies.get_strategies_for_failure(
            evidence.failure_class,
            self._budget,
        )

        if not strategies:
            result.status = RecoveryStatus.FAILED
            result.message = "No recovery strategies available"
            result.duration = time.time() - start
            return result

        # Try each strategy
        for cycle in range(self._max_recovery_cycles):
            if self._budget.exhausted:
                result.status = RecoveryStatus.EXHAUSTED
                break

            for strategy_option in strategies:
                if self._budget.exhausted:
                    break

                # Create recovery plan
                plan = self._planner.create_recovery_plan(
                    failure=evidence,
                    state=state,
                    available_capabilities=available_capabilities or [],
                )

                # Execute recovery action
                action = self._execute_recovery_action(
                    plan=plan,
                    state=state,
                    execute_fn=execute_fn,
                    context=context,
                )

                result.actions.append(action)
                state.add_recovery_action(action)

                if action.success:
                    result.status = RecoveryStatus.SUCCESS
                    result.final_output = action.result
                    result.message = f"Recovery successful: {action.description}"
                    result.budget_remaining = self._budget.to_dict()
                    result.duration = time.time() - start
                    return result

            # If no strategy worked, try replanning
            if not result.succeeded and self._budget.can_replan:
                self._budget.consume_replan()
                # Re-classify with accumulated evidence
                evidence = self._refine_failure_evidence(state)
                strategies = RecoveryStrategies.get_strategies_for_failure(
                    evidence.failure_class,
                    self._budget,
                )

        # Recovery failed
        if result.status != RecoveryStatus.SUCCESS:
            if self._budget.exhausted:
                result.status = RecoveryStatus.EXHAUSTED
                result.message = f"Recovery budget exhausted after {len(result.actions)} actions"
            else:
                result.status = RecoveryStatus.ESCALATED
                result.message = "Recovery failed - escalation required"

        result.budget_remaining = self._budget.to_dict()
        result.duration = time.time() - start
        return result

    def _execute_recovery_action(
        self,
        plan: RecoveryPlan,
        state: RecoveryState,
        execute_fn: Optional[Callable],
        context: Dict[str, Any],
    ) -> RecoveryAction:
        """Execute a single recovery action."""
        start = time.time()

        # Consume budget based on strategy
        if plan.strategy == RecoveryStrategyType.RETRY:
            if not self._budget.can_retry:
                return RecoveryAction(
                    strategy=plan.strategy,
                    description="Retry not available (budget exhausted)",
                    success=False,
                    duration=time.time() - start,
                )
            self._budget.consume_retry()

        elif plan.strategy == RecoveryStrategyType.REPLAN:
            if not self._budget.can_replan:
                return RecoveryAction(
                    strategy=plan.strategy,
                    description="Replan not available (budget exhausted)",
                    success=False,
                    duration=time.time() - start,
                )
            self._budget.consume_replan()

        elif plan.strategy == RecoveryStrategyType.BACKEND_SWITCH:
            if not self._budget.can_switch_backend:
                return RecoveryAction(
                    strategy=plan.strategy,
                    description="Backend switch not available (budget exhausted)",
                    success=False,
                    duration=time.time() - start,
                )
            self._budget.consume_backend_switch()

        elif plan.strategy == RecoveryStrategyType.REPAIR:
            if not self._budget.can_repair:
                return RecoveryAction(
                    strategy=plan.strategy,
                    description="Repair not available (budget exhausted)",
                    success=False,
                    duration=time.time() - start,
                )
            self._budget.consume_repair()

        # Execute the action
        result = None
        success = False
        error = None

        try:
            if execute_fn:
                exec_result = execute_fn(
                    capability_id=plan.capability_id,
                    input_data=plan.input_data,
                    strategy=plan.strategy,
                )
                if isinstance(exec_result, dict):
                    success = exec_result.get("success", False)
                    result = exec_result.get("output")
                    error = exec_result.get("error")
                else:
                    success = bool(exec_result)
                    result = exec_result
            else:
                # No execute function, just record the plan
                success = True
                result = plan.description

        except Exception as e:
            error = str(e)
            success = False

        action = RecoveryAction(
            strategy=plan.strategy,
            description=plan.description,
            input_data=plan.input_data,
            result=result,
            success=success,
            duration=time.time() - start,
        )

        # Record attempt
        state.add_attempt(AttemptRecord(
            attempt_number=state.attempt_count + 1,
            capability_id=plan.capability_id,
            input_data=plan.input_data,
            success=success,
            output=result,
            error=error,
            duration=action.duration,
        ))

        # Learn from failure
        if not success and error:
            state.add_learned_fact(f"Attempt {plan.strategy.value} failed: {error[:100]}")

        return action

    def _refine_failure_evidence(self, state: RecoveryState) -> FailureEvidence:
        """Refine failure evidence based on accumulated state."""
        # Use the most recent failure but update context with learned facts
        last_failure = state.last_failure
        if last_failure:
            context = dict(last_failure.context)
            context["learned_facts"] = state.learned_facts[-5:]
            context["attempt_count"] = state.attempt_count
            return FailureEvidence(
                failure_class=last_failure.failure_class,
                message=last_failure.message,
                command=last_failure.command,
                return_code=last_failure.return_code,
                context=context,
            )
        return FailureEvidence(
            failure_class=FailureClass.UNKNOWN,
            message="Unknown failure",
        )

    @property
    def budget(self) -> RecoveryBudget:
        return self._budget

    @property
    def state(self) -> Optional[RecoveryState]:
        return getattr(self, "_state", None)


def create_recovery_engine(
    budget: Optional[RecoveryBudget] = None,
    max_recovery_cycles: int = 5,
) -> RecoveryEngine:
    """Create a recovery engine with default configuration."""
    return RecoveryEngine(
        budget=budget or RecoveryBudget.default(),
        max_recovery_cycles=max_recovery_cycles,
    )