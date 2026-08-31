"""Benchmark comparison and baseline framework."""

from typing import Dict, List, Optional

from argus.benchmark.models import (
    BaselineResult,
    ComparisonResult,
    ExperimentResult,
    TaskRunResult,
)
from argus.benchmark.statistics import BenchmarkStatistics


class ComparisonError(Exception):
    """Error in comparison calculations."""
    pass


class ExperimentComparator:
    """Compares two or more experiment results."""

    def compare(
        self,
        experiment_a: ExperimentResult,
        experiment_b: ExperimentResult,
    ) -> ComparisonResult:
        """Compare two experiments and return detailed comparison."""
        metrics_a = self._extract_metrics(experiment_a.run_results)
        metrics_b = self._extract_metrics(experiment_b.run_results)

        comparison = ComparisonResult(
            experiment_a_id=experiment_a.config.experiment_id,
            experiment_b_id=experiment_b.config.experiment_id,
        )

        # Compare each metric
        all_metrics = set(metrics_a.keys()) | set(metrics_b.keys())
        for metric in all_metrics:
            val_a = metrics_a.get(metric, 0.0)
            val_b = metrics_b.get(metric, 0.0)

            comparison.metrics_comparison[metric] = {
                "a": val_a,
                "b": val_b,
            }
            comparison.absolute_differences[metric] = val_b - val_a

            if val_a != 0:
                comparison.relative_differences[metric] = (val_b - val_a) / val_a
            else:
                comparison.relative_differences[metric] = 0.0

            # Statistical significance for success rate
            if metric == "success_rate":
                sig = BenchmarkStatistics.compare_proportions(
                    int(val_a * len(experiment_a.run_results)),
                    len(experiment_a.run_results),
                    int(val_b * len(experiment_b.run_results)),
                    len(experiment_b.run_results),
                )
                comparison.statistically_significant[metric] = sig["significant"]
            else:
                comparison.statistically_significant[metric] = False

        comparison.conclusion = self._generate_conclusion(comparison)

        return comparison

    def _extract_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Extract comparable metrics from results."""
        if not results:
            return {
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "avg_tool_calls": 0.0,
                "avg_tokens": 0.0,
                "verification_rate": 0.0,
                "review_rate": 0.0,
            }

        total = len(results)
        successful = sum(1 for r in results if r.success)

        return {
            "success_rate": successful / total,
            "avg_duration": sum(r.duration_seconds for r in results) / total,
            "avg_tool_calls": sum(r.tool_calls for r in results) / total,
            "avg_tokens": sum(r.tokens_used for r in results) / total,
            "verification_rate": sum(1 for r in results if r.verification_passed) / total,
            "review_rate": sum(1 for r in results if r.review_passed) / total,
        }

    def _generate_conclusion(self, comparison: ComparisonResult) -> str:
        """Generate a human-readable conclusion from comparison."""
        success_diff = comparison.absolute_differences.get("success_rate", 0.0)
        significant = comparison.statistically_significant.get("success_rate", False)

        if abs(success_diff) < 0.02:
            base = "No meaningful difference in success rate"
        elif success_diff > 0:
            base = f"Configuration B shows +{success_diff:.1%} higher success rate"
        else:
            base = f"Configuration A shows +{abs(success_diff):.1%} higher success rate"

        if significant:
            base += " (statistically significant)"
        else:
            base += " (not statistically significant)"

        return base


class BaselineManager:
    """Manages baseline results for comparison."""

    def __init__(self):
        self._baselines: Dict[str, BaselineResult] = {}

    def register_baseline(self, baseline: BaselineResult) -> None:
        """Register a baseline result."""
        self._baselines[baseline.name] = baseline

    def get_baseline(self, name: str) -> Optional[BaselineResult]:
        """Get a baseline by name."""
        return self._baselines.get(name)

    def list_baselines(self) -> List[str]:
        """List all registered baseline names."""
        return list(self._baselines.keys())

    def compare_against_baseline(
        self,
        experiment: ExperimentResult,
        baseline_name: str,
    ) -> ComparisonResult:
        """Compare an experiment against a registered baseline."""
        baseline = self._baselines.get(baseline_name)
        if not baseline:
            raise ComparisonError(f"Baseline '{baseline_name}' not found")

        # Create a pseudo-experiment from baseline
        baseline_experiment = ExperimentResult(
            config=experiment.config,
            total_tasks=int(baseline.success_rate * 100),
            successful_tasks=int(baseline.success_rate * 100),
        )

        comparator = ExperimentComparator()
        return comparator.compare(experiment, baseline_experiment)


def create_default_baselines() -> BaselineManager:
    """Create a baseline manager with default baselines."""
    manager = BaselineManager()

    manager.register_baseline(BaselineResult(
        name="random_baseline",
        config={"type": "random"},
        success_rate=0.1,
        metrics={"description": "Random chance baseline"},
    ))

    manager.register_baseline(BaselineResult(
        name="gpt4_baseline",
        config={"type": "gpt-4"},
        success_rate=0.75,
        metrics={"description": "GPT-4 baseline performance"},
    ))

    return manager
