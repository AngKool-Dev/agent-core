"""Benchmark result aggregation."""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from argus.benchmark.models import (
    ExperimentResult,
    TaskCategory,
    TaskDifficulty,
    TaskRunResult,
    TaskTier,
)
from argus.benchmark.statistics import BenchmarkStatistics


class ResultAggregator:
    """Aggregates benchmark results across multiple dimensions."""

    def aggregate_by_category(
        self,
        results: List[TaskRunResult],
        task_categories: Dict[str, TaskCategory],
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate results by task category."""
        category_results: Dict[str, List[TaskRunResult]] = defaultdict(list)

        for result in results:
            category = task_categories.get(result.task_id)
            if category:
                category_results[category.value].append(result)

        return {
            cat: self._compute_aggregate(metrics)
            for cat, metrics in category_results.items()
        }

    def aggregate_by_difficulty(
        self,
        results: List[TaskRunResult],
        task_difficulties: Dict[str, TaskDifficulty],
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate results by task difficulty."""
        difficulty_results: Dict[str, List[TaskRunResult]] = defaultdict(list)

        for result in results:
            difficulty = task_difficulties.get(result.task_id)
            if difficulty:
                difficulty_results[difficulty.value].append(result)

        return {
            diff: self._compute_aggregate(metrics)
            for diff, metrics in difficulty_results.items()
        }

    def aggregate_by_tier(
        self,
        results: List[TaskRunResult],
        task_tiers: Dict[str, TaskTier],
    ) -> Dict[str, Dict[str, float]]:
        """Aggregate results by task tier."""
        tier_results: Dict[str, List[TaskRunResult]] = defaultdict(list)

        for result in results:
            tier = task_tiers.get(result.task_id)
            if tier:
                tier_results[tier.value].append(result)

        return {
            tier: self._compute_aggregate(metrics)
            for tier, metrics in tier_results.items()
        }

    def _compute_aggregate(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Compute aggregate metrics for a set of results."""
        if not results:
            return {
                "count": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "avg_tool_calls": 0.0,
                "avg_tokens": 0.0,
            }

        total = len(results)
        successful = sum(1 for r in results if r.success)

        return {
            "count": total,
            "success_rate": successful / total,
            "avg_duration": BenchmarkStatistics.mean([r.duration_seconds for r in results]),
            "avg_tool_calls": BenchmarkStatistics.mean([float(r.tool_calls) for r in results]),
            "avg_tokens": BenchmarkStatistics.mean([float(r.tokens_used) for r in results]),
        }

    def compute_learning_curve(
        self,
        results: List[TaskRunResult],
        task_difficulties: Dict[str, TaskDifficulty],
        difficulty_order: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute learning curve: performance as difficulty increases.

        Returns metrics for each difficulty level in order.
        """
        if difficulty_order is None:
            difficulty_order = ["easy", "medium", "hard", "expert"]

        curve = {}
        for difficulty in difficulty_order:
            diff_results = [
                r for r in results
                if task_difficulties.get(r.task_id) and
                task_difficulties[r.task_id].value == difficulty
            ]
            if diff_results:
                curve[difficulty] = self._compute_aggregate(diff_results)

        return curve

    def compute_percentiles(
        self,
        results: List[TaskRunResult],
    ) -> Dict[str, Dict[str, float]]:
        """Compute percentile distributions for key metrics."""
        if not results:
            return {}

        durations = [r.duration_seconds for r in results]
        tool_calls = [float(r.tool_calls) for r in results]
        tokens = [float(r.tokens_used) for r in results]

        return {
            "duration": {
                "p50": BenchmarkStatistics.percentile(durations, 50),
                "p75": BenchmarkStatistics.percentile(durations, 75),
                "p90": BenchmarkStatistics.percentile(durations, 90),
                "p95": BenchmarkStatistics.percentile(durations, 95),
                "p99": BenchmarkStatistics.percentile(durations, 99),
            },
            "tool_calls": {
                "p50": BenchmarkStatistics.percentile(tool_calls, 50),
                "p75": BenchmarkStatistics.percentile(tool_calls, 75),
                "p90": BenchmarkStatistics.percentile(tool_calls, 90),
                "p95": BenchmarkStatistics.percentile(tool_calls, 95),
                "p99": BenchmarkStatistics.percentile(tool_calls, 99),
            },
            "tokens": {
                "p50": BenchmarkStatistics.percentile(tokens, 50),
                "p75": BenchmarkStatistics.percentile(tokens, 75),
                "p90": BenchmarkStatistics.percentile(tokens, 90),
                "p95": BenchmarkStatistics.percentile(tokens, 95),
                "p99": BenchmarkStatistics.percentile(tokens, 99),
            },
        }
