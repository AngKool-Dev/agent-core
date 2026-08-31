"""Benchmark regression detection."""

from typing import Dict, List, Optional, Tuple

from argus.benchmark.models import (
    ComparisonResult,
    ExperimentResult,
    RegressionCheck,
    TaskRunResult,
)
from argus.benchmark.statistics import BenchmarkStatistics


class RegressionDetector:
    """Detects benchmark regressions."""

    def __init__(
        self,
        absolute_threshold: float = 0.05,
        relative_threshold: float = 0.10,
        confidence_threshold: float = 0.95,
    ):
        self._absolute_threshold = absolute_threshold
        self._relative_threshold = relative_threshold
        self._confidence_threshold = confidence_threshold

    def check_regression(
        self,
        baseline: List[TaskRunResult],
        current: List[TaskRunResult],
    ) -> Dict[str, RegressionCheck]:
        """Check for regressions between baseline and current results."""
        checks = {}

        # Check success rate regression
        baseline_success = sum(1 for r in baseline if r.success) / max(len(baseline), 1)
        current_success = sum(1 for r in current if r.success) / max(len(current), 1)
        checks["success_rate"] = self._create_regression_check(
            "success_rate",
            baseline_success,
            current_success,
        )

        # Check average duration regression
        baseline_duration = BenchmarkStatistics.mean([r.duration_seconds for r in baseline])
        current_duration = BenchmarkStatistics.mean([r.duration_seconds for r in current])
        checks["avg_duration"] = self._create_regression_check(
            "avg_duration",
            baseline_duration,
            current_duration,
        )

        # Check average tool calls regression
        baseline_tools = BenchmarkStatistics.mean([float(r.tool_calls) for r in baseline])
        current_tools = BenchmarkStatistics.mean([float(r.tool_calls) for r in current])
        checks["avg_tool_calls"] = self._create_regression_check(
            "avg_tool_calls",
            baseline_tools,
            current_tools,
        )

        return checks

    def _create_regression_check(
        self,
        metric: str,
        baseline_value: float,
        current_value: float,
    ) -> RegressionCheck:
        """Create a regression check for a metric."""
        absolute_change = current_value - baseline_value
        relative_change = absolute_change / baseline_value if baseline_value != 0 else 0.0

        # For metrics where lower is better (duration, tool calls)
        # regression = increase
        # For metrics where higher is better (success rate)
        # regression = decrease
        is_regression = False
        if metric == "success_rate":
            is_regression = absolute_change < -self._absolute_threshold
        else:
            is_regression = relative_change > self._relative_threshold

        return RegressionCheck(
            metric=metric,
            baseline_value=baseline_value,
            current_value=current_value,
            absolute_change=absolute_change,
            relative_change=relative_change,
            is_regression=is_regression,
            threshold=self._absolute_threshold,
            confidence=self._confidence_threshold,
        )

    def has_regression(
        self,
        baseline: List[TaskRunResult],
        current: List[TaskRunResult],
    ) -> bool:
        """Check if any regression was detected."""
        checks = self.check_regression(baseline, current)
        return any(check.is_regression for check in checks.values())

    def get_regression_summary(
        self,
        baseline: List[TaskRunResult],
        current: List[TaskRunResult],
    ) -> Dict[str, any]:
        """Get a summary of regression checks."""
        checks = self.check_regression(baseline, current)
        regressions = {k: v for k, v in checks.items() if v.is_regression}

        return {
            "total_checks": len(checks),
            "regressions_found": len(regressions),
            "regressions": {
                k: {
                    "baseline": v.baseline_value,
                    "current": v.current_value,
                    "absolute_change": v.absolute_change,
                    "relative_change": v.relative_change,
                }
                for k, v in regressions.items()
            },
            "checks": {
                k: {
                    "baseline": v.baseline_value,
                    "current": v.current_value,
                    "is_regression": v.is_regression,
                }
                for k, v in checks.items()
            },
        }
