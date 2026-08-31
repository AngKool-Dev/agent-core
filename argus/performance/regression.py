"""Performance regression detection."""

from typing import Dict, List, Optional

from argus.performance.models import PerformanceMeasurement, MeasurementType


class PerformanceRegressionDetector:
    """Detects performance regressions."""

    def __init__(
        self,
        latency_threshold: float = 1.5,  # 50% increase
        throughput_threshold: float = 0.7,  # 30% decrease
        error_rate_threshold: float = 0.1,  # 10% error rate
    ):
        self._latency_threshold = latency_threshold
        self._throughput_threshold = throughput_threshold
        self._error_rate_threshold = error_rate_threshold

    def check_latency_regression(
        self,
        baseline: List[float],
        current: List[float],
    ) -> Dict[str, any]:
        """Check for latency regression."""
        if not baseline or not current:
            return {"is_regression": False, "reason": "insufficient_data"}

        baseline_avg = sum(baseline) / len(baseline)
        current_avg = sum(current) / len(current)

        if baseline_avg == 0:
            return {"is_regression": False, "reason": "zero_baseline"}

        ratio = current_avg / baseline_avg
        is_regression = ratio > self._latency_threshold

        return {
            "is_regression": is_regression,
            "baseline_avg": baseline_avg,
            "current_avg": current_avg,
            "ratio": ratio,
            "threshold": self._latency_threshold,
        }

    def check_throughput_regression(
        self,
        baseline: List[float],
        current: List[float],
    ) -> Dict[str, any]:
        """Check for throughput regression."""
        if not baseline or not current:
            return {"is_regression": False, "reason": "insufficient_data"}

        baseline_avg = sum(baseline) / len(baseline)
        current_avg = sum(current) / len(current)

        if baseline_avg == 0:
            return {"is_regression": False, "reason": "zero_baseline"}

        ratio = current_avg / baseline_avg
        is_regression = ratio < self._throughput_threshold

        return {
            "is_regression": is_regression,
            "baseline_avg": baseline_avg,
            "current_avg": current_avg,
            "ratio": ratio,
            "threshold": self._throughput_threshold,
        }

    def check_error_rate_regression(
        self,
        baseline_errors: int,
        baseline_total: int,
        current_errors: int,
        current_total: int,
    ) -> Dict[str, any]:
        """Check for error rate regression."""
        if baseline_total == 0 or current_total == 0:
            return {"is_regression": False, "reason": "insufficient_data"}

        baseline_rate = baseline_errors / baseline_total
        current_rate = current_errors / current_total

        is_regression = current_rate > max(
            baseline_rate + self._error_rate_threshold,
            self._error_rate_threshold,
        )

        return {
            "is_regression": is_regression,
            "baseline_rate": baseline_rate,
            "current_rate": current_rate,
            "threshold": self._error_rate_threshold,
        }

    def analyze_measurements(
        self,
        baseline: List[PerformanceMeasurement],
        current: List[PerformanceMeasurement],
    ) -> Dict[str, any]:
        """Analyze measurements for regressions."""
        baseline_values = [m.value for m in baseline]
        current_values = [m.value for m in current]

        return {
            "latency": self.check_latency_regression(baseline_values, current_values),
            "sample_size": {
                "baseline": len(baseline),
                "current": len(current),
            },
        }
