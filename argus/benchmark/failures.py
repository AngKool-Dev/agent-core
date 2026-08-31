"""Failure taxonomy and analysis for benchmark results."""

from collections import Counter
from typing import Dict, List, Optional, Tuple

from argus.benchmark.models import (
    FailureRecord,
    FailureType,
    InfrastructureType,
    TaskRunResult,
)


class FailureAnalyzer:
    """Analyzes and classifies benchmark failures."""

    def analyze_failure(
        self,
        result: TaskRunResult,
        task_context: Optional[Dict] = None,
    ) -> FailureRecord:
        """Analyze a single task failure and classify it."""
        record = FailureRecord(
            task_id=result.task_id,
            experiment_id=result.experiment_id,
            error_message=result.error or "",
        )

        # Determine infrastructure type
        record.infrastructure_type = self._classify_infrastructure_type(result)

        # Determine failure type
        record.failure_type = self._classify_failure_type(result)

        # Determine if failure was recoverable
        record.recovery_attempted = result.recovery_attempts > 0
        record.recovery_succeeded = result.recovery_attempts > 0 and result.success

        # Determine initial vs fatal failure
        if result.recovery_attempts > 0:
            record.initial_failure = result.failure_type.value if result.failure_type else "unknown"
            record.fatal_failure = "recovery_exhausted" if not result.success else ""
        else:
            record.initial_failure = result.failure_type.value if result.failure_type else "unknown"
            record.fatal_failure = record.initial_failure

        if task_context:
            record.context = task_context

        return record

    def _classify_infrastructure_type(
        self, result: TaskRunResult
    ) -> InfrastructureType:
        """Classify whether failure is infrastructure or agent-related."""
        if result.infrastructure_type:
            return result.infrastructure_type

        # Heuristic classification
        if result.provider_failures > 0:
            return InfrastructureType.PROVIDER_FAILURE
        if result.error and "environment" in result.error.lower():
            return InfrastructureType.ENVIRONMENT_FAILURE
        if result.error and "harness" in result.error.lower():
            return InfrastructureType.HARNESS_FAILURE

        return InfrastructureType.AGENT_FAILURE

    def _classify_failure_type(self, result: TaskRunResult) -> FailureType:
        """Classify the type of failure."""
        if result.failure_type:
            return result.failure_type

        # Heuristic classification based on result attributes
        # Check for specific failure types first
        if result.provider_failures > 0:
            return FailureType.PROVIDER_FAILURE
        if result.security_blocks > 0 and not result.success:
            return FailureType.SECURITY_BLOCK
        if result.recovery_attempts > 0 and not result.success:
            return FailureType.RECOVERY_EXHAUSTION
        if result.error:
            error_lower = result.error.lower()
            if "planning" in error_lower:
                return FailureType.PLANNING_FAILURE
            if "context" in error_lower:
                return FailureType.CONTEXT_FAILURE
            if "model" in error_lower:
                return FailureType.MODEL_FAILURE
            if "tool" in error_lower:
                return FailureType.TOOL_FAILURE
            if "crash" in error_lower or "durability" in error_lower:
                return FailureType.DURABILITY_FAILURE
            if "verification" in error_lower:
                return FailureType.VERIFICATION_FAILURE
            if "review" in error_lower:
                return FailureType.REVIEW_FAILURE

        # Fallback to checking verification/review status
        if not result.verification_passed:
            return FailureType.VERIFICATION_FAILURE
        if not result.review_passed:
            return FailureType.REVIEW_FAILURE

        return FailureType.UNKNOWN_FAILURE

    def analyze_failures(
        self,
        results: List[TaskRunResult],
    ) -> List[FailureRecord]:
        """Analyze all failed results."""
        failed = [r for r in results if not r.success]
        return [self.analyze_failure(r) for r in failed]

    def get_failure_distribution(
        self,
        results: List[TaskRunResult],
    ) -> Dict[str, int]:
        """Get distribution of failure types."""
        records = self.analyze_failures(results)
        distribution = Counter()
        for record in records:
            distribution[record.failure_type.value] += 1
        return dict(distribution)

    def get_infrastructure_distribution(
        self,
        results: List[TaskRunResult],
    ) -> Dict[str, int]:
        """Get distribution of infrastructure types."""
        records = self.analyze_failures(results)
        distribution = Counter()
        for record in records:
            if record.infrastructure_type:
                distribution[record.infrastructure_type.value] += 1
        return dict(distribution)

    def get_error_budget_analysis(
        self,
        results: List[TaskRunResult],
    ) -> Dict[str, any]:
        """Analyze where tasks are lost in the pipeline."""
        failed = [r for r in results if not r.success]

        analysis = {
            "total_failed": len(failed),
            "first_failures": {},
            "fatal_failures": {},
            "recoverable_failures": 0,
            "unrecoverable_failures": 0,
        }

        for result in failed:
            record = self.analyze_failure(result)

            # Count first failures
            first = record.initial_failure
            analysis["first_failures"][first] = analysis["first_failures"].get(first, 0) + 1

            # Count fatal failures
            fatal = record.fatal_failure
            analysis["fatal_failures"][fatal] = analysis["fatal_failures"].get(fatal, 0) + 1

            # Recoverable vs unrecoverable
            if record.recovery_attempted and record.recovery_succeeded:
                analysis["recoverable_failures"] += 1
            else:
                analysis["unrecoverable_failures"] += 1

        return analysis

    def get_failure_summary(
        self,
        results: List[TaskRunResult],
    ) -> Dict[str, any]:
        """Generate a comprehensive failure summary."""
        failed = [r for r in results if not r.success]
        total = len(results)

        return {
            "total_tasks": total,
            "failed_tasks": len(failed),
            "failure_rate": len(failed) / total if total > 0 else 0.0,
            "failure_distribution": self.get_failure_distribution(results),
            "infrastructure_distribution": self.get_infrastructure_distribution(results),
            "error_budget": self.get_error_budget_analysis(results),
        }
