"""Main benchmark evaluator that orchestrates the evaluation process."""

from typing import Any, Dict, List, Optional

from argus.benchmark.aggregation import ResultAggregator
from argus.benchmark.baselines import RegressionDetector
from argus.benchmark.comparison import ExperimentComparator
from argus.benchmark.dataset import get_default_dataset
from argus.benchmark.failures import FailureAnalyzer
from argus.benchmark.metrics import MetricsCalculator
from argus.benchmark.models import (
    BenchmarkDataset,
    BenchmarkScore,
    ExperimentConfig,
    ExperimentResult,
    TaskRunResult,
)
from argus.benchmark.reporter import BenchmarkReporter
from argus.benchmark.reproducibility import ReproducibilityManager
from argus.benchmark.scoring import BenchmarkScorer, create_default_scorer
from argus.benchmark.statistics import BenchmarkStatistics


class BenchmarkEvaluator:
    """
    Main evaluator for ARGUS benchmarks.

    Orchestrates the evaluation process including:
    - Running experiments
    - Calculating metrics
    - Scoring results
    - Detecting regressions
    - Generating reports
    """

    def __init__(
        self,
        scorer: Optional[BenchmarkScorer] = None,
        regression_threshold: float = 0.05,
    ):
        self._scorer = scorer or create_default_scorer()
        self._metrics_calc = MetricsCalculator()
        self._reporter = BenchmarkReporter()
        self._failure_analyzer = FailureAnalyzer()
        self._comparator = ExperimentComparator()
        self._aggregator = ResultAggregator()
        self._reproducibility = ReproducibilityManager()
        self._regression_detector = RegressionDetector(
            absolute_threshold=regression_threshold
        )
        self._experiment_history: List[ExperimentResult] = []

    def run_experiment(
        self,
        config: ExperimentConfig,
        dataset: Optional[BenchmarkDataset] = None,
        task_results: Optional[List[TaskRunResult]] = None,
    ) -> ExperimentResult:
        """
        Run a benchmark experiment.

        If task_results is provided, uses those directly.
        Otherwise, creates placeholder results based on config.
        """
        if dataset is None:
            dataset = get_default_dataset()

        if task_results is None:
            task_results = self._create_placeholder_results(config, dataset)

        # Build experiment result
        experiment = ExperimentResult(
            config=config,
            run_results=task_results,
            total_tasks=len(task_results),
            successful_tasks=sum(1 for r in task_results if r.success),
            failed_tasks=sum(1 for r in task_results if not r.success),
            total_duration=sum(r.duration_seconds for r in task_results),
            total_iterations=sum(r.iterations for r in task_results),
            total_tool_calls=sum(r.tool_calls for r in task_results),
            total_model_calls=sum(r.model_calls for r in task_results),
            total_tokens=sum(r.tokens_used for r in task_results),
            total_recovery_attempts=sum(r.recovery_attempts for r in task_results),
            total_security_blocks=sum(r.security_blocks for r in task_results),
            total_provider_failures=sum(r.provider_failures for r in task_results),
            total_crash_resumes=sum(r.crash_resumes for r in task_results),
        )

        # Store in history
        self._experiment_history.append(experiment)

        return experiment

    def _create_placeholder_results(
        self,
        config: ExperimentConfig,
        dataset: BenchmarkDataset,
    ) -> List[TaskRunResult]:
        """Create placeholder results for testing."""
        results = []
        for task in dataset.tasks:
            for _ in range(config.repeat_count):
                result = TaskRunResult(
                    task_id=task.task_id,
                    experiment_id=config.experiment_id,
                    success=True,
                    duration_seconds=1.0,
                    iterations=1,
                    tool_calls=1,
                    tokens_used=100,
                    score=1.0,
                )
                results.append(result)
        return results

    def score_experiment(self, experiment: ExperimentResult) -> BenchmarkScore:
        """Score an experiment."""
        return self._scorer.score_experiment(experiment)

    def get_metrics(
        self, experiment: ExperimentResult
    ) -> Dict[str, Dict[str, float]]:
        """Get all metrics for an experiment."""
        return self._metrics_calc.calculate_all_metrics(experiment.run_results)

    def get_failure_analysis(
        self, experiment: ExperimentResult
    ) -> Dict[str, Any]:
        """Get failure analysis for an experiment."""
        return self._failure_analyzer.get_failure_summary(experiment.run_results)

    def compare_experiments(
        self,
        experiment_a: ExperimentResult,
        experiment_b: ExperimentResult,
    ):
        """Compare two experiments."""
        return self._comparator.compare(experiment_a, experiment_b)

    def check_regression(
        self,
        baseline: ExperimentResult,
        current: ExperimentResult,
    ) -> Dict[str, Any]:
        """Check for regressions between experiments."""
        return self._regression_detector.get_regression_summary(
            baseline.run_results,
            current.run_results,
        )

    def get_statistics(
        self, experiment: ExperimentResult
    ) -> Dict[str, Any]:
        """Get statistical summaries for an experiment."""
        results = experiment.run_results
        return {
            "duration": BenchmarkStatistics.summarize(
                [r.duration_seconds for r in results]
            ),
            "tool_calls": BenchmarkStatistics.summarize(
                [float(r.tool_calls) for r in results]
            ),
            "tokens": BenchmarkStatistics.summarize(
                [float(r.tokens_used) for r in results]
            ),
            "scores": BenchmarkStatistics.summarize(
                [r.score for r in results]
            ),
        }

    def generate_report(
        self,
        experiment: ExperimentResult,
        format: str = "text",
    ) -> str:
        """Generate a report for an experiment."""
        score = self.score_experiment(experiment)

        if format == "json":
            import json
            report = self._reporter.generate_json_report(experiment, score)
            return json.dumps(report, indent=2, default=str)
        elif format == "markdown":
            return self._reporter.generate_markdown_report(experiment, score)
        else:
            return self._reporter.generate_text_report(experiment, score)

    def get_experiment_history(self) -> List[ExperimentResult]:
        """Get the history of all experiments."""
        return self._experiment_history.copy()

    def clear_history(self) -> None:
        """Clear experiment history."""
        self._experiment_history.clear()
