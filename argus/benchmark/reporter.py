"""Benchmark reporting system."""

import json
from datetime import datetime
from typing import Dict, List, Optional

from argus.benchmark.models import (
    BenchmarkScore,
    ComparisonResult,
    ExperimentResult,
    TaskRunResult,
)
from argus.benchmark.metrics import MetricsCalculator


class BenchmarkReporter:
    """Generates benchmark reports in multiple formats."""

    def __init__(self):
        self._metrics_calc = MetricsCalculator()

    def generate_text_report(
        self,
        experiment: ExperimentResult,
        score: Optional[BenchmarkScore] = None,
    ) -> str:
        """Generate a human-readable text report."""
        metrics = self._metrics_calc.calculate_all_metrics(experiment.run_results)

        lines = [
            "ARGUS BENCHMARK",
            "=" * 50,
            "",
            f"Experiment: {experiment.config.experiment_id}",
            f"Benchmark: {experiment.config.benchmark_version}",
            f"Tasks: {experiment.total_tasks}",
            f"Repeats: {experiment.config.repeat_count}",
            "",
            "SUCCESS",
            "-" * 30,
            f"Overall: {metrics['primary']['success_rate']:.1%}",
            f"Pass@1: {metrics['primary']['pass_at_1']:.1%}",
            f"Verification: {metrics['primary']['verification_pass_rate']:.1%}",
            f"Review: {metrics['primary']['review_pass_rate']:.1%}",
            f"Recovery: {metrics['primary']['recovery_success_rate']:.1%}",
            "",
            "EFFICIENCY",
            "-" * 30,
            f"Median duration: {metrics['efficiency']['avg_duration_per_task']:.2f}s",
            f"Median tokens: {metrics['efficiency']['avg_tokens_per_task']:.0f}",
            f"Median tool calls: {metrics['efficiency']['avg_tool_calls_per_task']:.1f}",
            f"Average iterations: {metrics['efficiency']['avg_iterations_per_task']:.1f}",
            "",
            "SECURITY",
            "-" * 30,
            f"Attack block rate: {metrics['security']['attack_block_rate']:.1%}",
            f"False positive rate: {metrics['security']['false_positive_rate']:.1%}",
            "",
            "PROVIDER",
            "-" * 30,
            f"Failures: {metrics['provider']['total_provider_failures']}",
            f"Fallbacks: {metrics['provider']['total_fallbacks']}",
            f"Switches: {metrics['provider']['total_provider_switches']}",
            "",
            "DURABILITY",
            "-" * 30,
            f"Crashes injected: {metrics['durability']['total_crashes_injected']}",
            f"Successful resumes: {metrics['durability']['successful_resumes']}",
            f"Duplicate executions: {metrics['durability']['duplicate_executions']}",
        ]

        if score:
            lines.extend([
                "",
                "SCORE",
                "-" * 30,
                f"Final score: {score.final_score:.3f}",
                f"Sample size: {score.sample_size}",
            ])
            if score.confidence_interval:
                lines.append(
                    f"95% CI: [{score.confidence_interval[0]:.3f}, {score.confidence_interval[1]:.3f}]"
                )

        lines.extend([
            "",
            f"Report generated: {datetime.utcnow().isoformat()}",
        ])

        return "\n".join(lines)

    def generate_markdown_report(
        self,
        experiment: ExperimentResult,
        score: Optional[BenchmarkScore] = None,
    ) -> str:
        """Generate a Markdown report."""
        metrics = self._metrics_calc.calculate_all_metrics(experiment.run_results)

        lines = [
            f"# ARGUS Benchmark Report",
            "",
            f"**Experiment:** {experiment.config.experiment_id}",
            f"**Benchmark:** {experiment.config.benchmark_version}",
            f"**Tasks:** {experiment.total_tasks}",
            f"**Repeats:** {experiment.config.repeat_count}",
            "",
            "## Success Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Overall Success | {metrics['primary']['success_rate']:.1%} |",
            f"| Pass@1 | {metrics['primary']['pass_at_1']:.1%} |",
            f"| Verification | {metrics['primary']['verification_pass_rate']:.1%} |",
            f"| Review | {metrics['primary']['review_pass_rate']:.1%} |",
            f"| Recovery | {metrics['primary']['recovery_success_rate']:.1%} |",
            "",
            "## Efficiency Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Avg Duration | {metrics['efficiency']['avg_duration_per_task']:.2f}s |",
            f"| Avg Tokens | {metrics['efficiency']['avg_tokens_per_task']:.0f} |",
            f"| Avg Tool Calls | {metrics['efficiency']['avg_tool_calls_per_task']:.1f} |",
            f"| Avg Iterations | {metrics['efficiency']['avg_iterations_per_task']:.1f} |",
            "",
            "## Security Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Attack Block Rate | {metrics['security']['attack_block_rate']:.1%} |",
            f"| False Positive Rate | {metrics['security']['false_positive_rate']:.1%} |",
        ]

        if score:
            lines.extend([
                "",
                "## Score",
                "",
                f"**Final Score:** {score.final_score:.3f}",
                f"**Sample Size:** {score.sample_size}",
            ])
            if score.confidence_interval:
                lines.append(
                    f"**95% CI:** [{score.confidence_interval[0]:.3f}, {score.confidence_interval[1]:.3f}]"
                )

        lines.extend([
            "",
            f"*Report generated: {datetime.utcnow().isoformat()}*",
        ])

        return "\n".join(lines)

    def generate_json_report(
        self,
        experiment: ExperimentResult,
        score: Optional[BenchmarkScore] = None,
    ) -> Dict:
        """Generate a JSON-serializable report."""
        metrics = self._metrics_calc.calculate_all_metrics(experiment.run_results)

        report = {
            "experiment_id": experiment.config.experiment_id,
            "benchmark_version": experiment.config.benchmark_version,
            "configuration": {
                "provider": experiment.config.provider,
                "model": experiment.config.model,
                "temperature": experiment.config.temperature,
                "seed": experiment.config.seed,
                "repeat_count": experiment.config.repeat_count,
            },
            "summary": {
                "total_tasks": experiment.total_tasks,
                "successful_tasks": experiment.successful_tasks,
                "failed_tasks": experiment.failed_tasks,
            },
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if score:
            report["score"] = {
                "final_score": score.final_score,
                "raw_metrics": score.raw_metrics,
                "weighted_components": score.weighted_components,
                "confidence_interval": score.confidence_interval,
                "sample_size": score.sample_size,
            }

        return report

    def generate_csv_data(
        self,
        experiment: ExperimentResult,
    ) -> List[Dict]:
        """Generate CSV-compatible data."""
        rows = []
        for result in experiment.run_results:
            rows.append({
                "experiment_id": experiment.config.experiment_id,
                "run_id": result.run_id,
                "task_id": result.task_id,
                "success": result.success,
                "duration_seconds": result.duration_seconds,
                "iterations": result.iterations,
                "tool_calls": result.tool_calls,
                "tokens_used": result.tokens_used,
                "verification_passed": result.verification_passed,
                "review_passed": result.review_passed,
                "recovery_attempts": result.recovery_attempts,
                "security_blocks": result.security_blocks,
                "score": result.score,
            })
        return rows
