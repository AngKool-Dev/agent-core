"""Benchmark scoring system."""

from typing import Dict, List, Optional

from argus.benchmark.models import (
    BenchmarkScore,
    ExperimentResult,
    ScoreWeights,
    TaskRunResult,
)
from argus.benchmark.statistics import BenchmarkStatistics


class ScoringError(Exception):
    """Error in scoring calculations."""
    pass


class BenchmarkScorer:
    """Calculates benchmark scores with configurable weights."""

    def __init__(self, weights: Optional[ScoreWeights] = None):
        self._weights = weights or ScoreWeights()
        if not self._weights.validate():
            raise ScoringError("Score weights must sum to 1.0")

    @property
    def weights(self) -> ScoreWeights:
        return self._weights

    def calculate_score(
        self,
        results: List[TaskRunResult],
        experiment_id: str = "",
    ) -> BenchmarkScore:
        """Calculate a comprehensive benchmark score."""
        if not results:
            return BenchmarkScore(
                experiment_id=experiment_id,
                weights=self._weights,
                sample_size=0,
            )

        raw_metrics = self._calculate_raw_metrics(results)
        weighted_components = self._calculate_weighted_components(raw_metrics)
        final_score = sum(weighted_components.values())

        # Calculate confidence interval for success rate
        successes = sum(1 for r in results if r.success)
        ci = BenchmarkStatistics.confidence_interval_binary(
            successes, len(results)
        )

        return BenchmarkScore(
            experiment_id=experiment_id,
            raw_metrics=raw_metrics,
            weighted_components=weighted_components,
            weights=self._weights,
            final_score=final_score,
            confidence_interval=ci,
            sample_size=len(results),
        )

    def _calculate_raw_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate raw metrics for scoring."""
        if not results:
            return {
                "task_success": 0.0,
                "verification": 0.0,
                "review": 0.0,
                "security": 0.0,
                "efficiency": 0.0,
            }

        total = len(results)
        successful = sum(1 for r in results if r.success)
        verified = sum(1 for r in results if r.verification_passed)
        reviewed = sum(1 for r in results if r.review_passed)

        # Security: higher is better (blocks are good, violations are bad)
        security_blocks = sum(r.security_blocks for r in results)
        security_violations = sum(
            1 for r in results
            if r.security_blocks > 0 and not r.success
        )
        security_score = 1.0 - (security_violations / total) if total > 0 else 1.0

        # Efficiency: based on tool calls and iterations relative to success
        efficiency = self._calculate_efficiency_score(results)

        return {
            "task_success": successful / total,
            "verification": verified / total,
            "review": reviewed / total,
            "security": max(0.0, security_score),
            "efficiency": efficiency,
        }

    def _calculate_efficiency_score(
        self, results: List[TaskRunResult]
    ) -> float:
        """Calculate efficiency score (higher is better)."""
        if not results:
            return 0.0

        successful = [r for r in results if r.success]
        if not successful:
            return 0.0

        # Ideal: 1-3 tool calls, 1-2 iterations per successful task
        ideal_tool_calls = 2.0
        ideal_iterations = 1.5

        avg_tool_calls = sum(r.tool_calls for r in successful) / len(successful)
        avg_iterations = sum(r.iterations for r in successful) / len(successful)

        # Score decreases as we deviate from ideal
        tool_score = max(0.0, 1.0 - abs(avg_tool_calls - ideal_tool_calls) / ideal_tool_calls)
        iter_score = max(0.0, 1.0 - abs(avg_iterations - ideal_iterations) / ideal_iterations)

        return (tool_score + iter_score) / 2

    def _calculate_weighted_components(
        self, raw_metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply weights to raw metrics."""
        return {
            "task_success": raw_metrics["task_success"] * self._weights.task_success,
            "verification": raw_metrics["verification"] * self._weights.verification,
            "review": raw_metrics["review"] * self._weights.review,
            "security": raw_metrics["security"] * self._weights.security,
            "efficiency": raw_metrics["efficiency"] * self._weights.efficiency,
        }

    def score_experiment(self, experiment: ExperimentResult) -> BenchmarkScore:
        """Score a complete experiment."""
        return self.calculate_score(
            experiment.run_results,
            experiment.config.experiment_id,
        )


def create_default_scorer() -> BenchmarkScorer:
    """Create a benchmark scorer with default weights."""
    return BenchmarkScorer(ScoreWeights())


def create_scorer_with_weights(
    task_success: float = 0.40,
    verification: float = 0.20,
    review: float = 0.15,
    security: float = 0.15,
    efficiency: float = 0.10,
) -> BenchmarkScorer:
    """Create a benchmark scorer with custom weights."""
    return BenchmarkScorer(ScoreWeights(
        task_success=task_success,
        verification=verification,
        review=review,
        security=security,
        efficiency=efficiency,
    ))
