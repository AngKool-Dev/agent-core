"""Recovery strategies - different approaches to recover from failures."""

from typing import Any, Callable, Dict, List, Optional

from argus.recovery.budget import RecoveryBudget
from argus.recovery.result import (
    FailureClass,
    FailureEvidence,
    RecoveryAction,
    RecoveryStrategyType,
    RecoveryStatus,
)


class RecoveryOption:
    """A possible recovery option."""

    def __init__(
        self,
        strategy: RecoveryStrategyType,
        description: str,
        priority: int = 0,
        available: bool = True,
        action_fn: Optional[Callable] = None,
    ):
        self.strategy = strategy
        self.description = description
        self.priority = priority
        self.available = available
        self.action_fn = action_fn


class RecoveryStrategies:
    """Collection of recovery strategies."""

    @staticmethod
    def get_strategies_for_failure(
        failure_class: FailureClass,
        budget: RecoveryBudget,
    ) -> List[RecoveryOption]:
        """Get available recovery strategies for a failure class."""
        strategies: List[RecoveryOption] = []

        if failure_class == FailureClass.TRANSIENT:
            # Transient failures: retry, then backend switch
            if budget.can_retry:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.RETRY,
                    description="Retry the operation (transient failure)",
                    priority=10,
                ))
            if budget.can_switch_backend:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.BACKEND_SWITCH,
                    description="Switch to alternative backend",
                    priority=5,
                ))

        elif failure_class == FailureClass.BACKEND:
            # Backend failures: switch backend, then fallback
            if budget.can_switch_backend:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.BACKEND_SWITCH,
                    description="Switch to alternative backend",
                    priority=10,
                ))
            if budget.can_retry:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.RETRY,
                    description="Retry (may be temporary)",
                    priority=5,
                ))
            strategies.append(RecoveryOption(
                strategy=RecoveryStrategyType.FALLBACK,
                description="Use fallback capability",
                priority=3,
            ))

        elif failure_class == FailureClass.EXECUTION:
            # Execution failures: repair, then retry
            if budget.can_repair:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPAIR,
                    description="Repair the execution environment",
                    priority=10,
                ))
            if budget.can_retry:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.RETRY,
                    description="Retry after repair",
                    priority=5,
                ))
            if budget.can_replan:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPLAN,
                    description="Replan with different approach",
                    priority=3,
                ))

        elif failure_class == FailureClass.CODE:
            # Code failures: repair, then replan
            if budget.can_repair:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPAIR,
                    description="Repair the code issue",
                    priority=10,
                ))
            if budget.can_replan:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPLAN,
                    description="Replan with corrected approach",
                    priority=5,
                ))
            if budget.can_retry:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.RETRY,
                    description="Retry after repair",
                    priority=3,
                ))

        elif failure_class == FailureClass.LOGICAL:
            # Logical failures: replan, then repair
            if budget.can_replan:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPLAN,
                    description="Replan with corrected logic",
                    priority=10,
                ))
            if budget.can_repair:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPAIR,
                    description="Repair based on verification feedback",
                    priority=5,
                ))

        elif failure_class == FailureClass.ENVIRONMENT:
            # Environment failures: repair, then escalate
            if budget.can_repair:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPAIR,
                    description="Fix environment issue",
                    priority=10,
                ))
            strategies.append(RecoveryOption(
                strategy=RecoveryStrategyType.ESCALATE,
                description="Escalate to user (environment issue)",
                priority=5,
            ))

        elif failure_class == FailureClass.USER_REQUIRED:
            # User required: escalate
            strategies.append(RecoveryOption(
                strategy=RecoveryStrategyType.ESCALATE,
                description="Escalate to user (requires user input)",
                priority=10,
            ))

        else:  # UNKNOWN
            # Unknown: try retry, then replan, then escalate
            if budget.can_retry:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.RETRY,
                    description="Retry (unknown failure)",
                    priority=10,
                ))
            if budget.can_replan:
                strategies.append(RecoveryOption(
                    strategy=RecoveryStrategyType.REPLAN,
                    description="Replan with different approach",
                    priority=5,
                ))
            strategies.append(RecoveryOption(
                strategy=RecoveryStrategyType.ESCALATE,
                description="Escalate to user",
                priority=1,
            ))

        # Sort by priority
        strategies.sort(key=lambda s: s.priority, reverse=True)
        return strategies

    @staticmethod
    def select_best_strategy(
        failure_class: FailureClass,
        budget: RecoveryBudget,
    ) -> Optional[RecoveryStrategyType]:
        """Select the best recovery strategy for a failure."""
        strategies = RecoveryStrategies.get_strategies_for_failure(failure_class, budget)
        if strategies:
            return strategies[0].strategy
        return None