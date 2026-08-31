"""Benchmark CLI commands for ARGUS."""

import argparse
import json
import sys
from typing import List, Optional

from argus.benchmark.dataset import get_default_dataset
from argus.benchmark.export import BenchmarkExporter
from argus.benchmark.models import (
    BenchmarkStatus,
    ExperimentConfig,
    ExperimentResult,
    TaskRunResult,
)
from argus.benchmark.reporter import BenchmarkReporter
from argus.benchmark.scoring import create_default_scorer


def handle_command(repl, args: List[str]) -> str:
    """Handle /benchmark command."""
    parser = argparse.ArgumentParser(prog="/benchmark", description="ARGUS Benchmark")
    subparsers = parser.add_subparsers(dest="action")

    # /benchmark list
    subparsers.add_parser("list", help="List available benchmarks")

    # /benchmark run
    run_parser = subparsers.add_parser("run", help="Run a benchmark")
    run_parser.add_argument("benchmark", nargs="?", default="engineering-v1.0")
    run_parser.add_argument("--provider", default="")
    run_parser.add_argument("--model", default="")
    run_parser.add_argument("--tasks", nargs="*", default=[])
    run_parser.add_argument("--difficulty", default="")
    run_parser.add_argument("--category", default="")
    run_parser.add_argument("--repeat", type=int, default=1)
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--timeout", type=int, default=300)
    run_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    run_parser.add_argument("--output", default="")
    run_parser.add_argument("--ci", action="store_true")

    # /benchmark task
    task_parser = subparsers.add_parser("task", help="Show task details")
    task_parser.add_argument("task_id", help="Task ID")

    # /benchmark results
    subparsers.add_parser("results", help="Show recent results")

    # /benchmark compare
    compare_parser = subparsers.add_parser("compare", help="Compare experiments")
    compare_parser.add_argument("experiment_a", help="First experiment ID")
    compare_parser.add_argument("experiment_b", help="Second experiment ID")

    # /benchmark export
    export_parser = subparsers.add_parser("export", help="Export results")
    export_parser.add_argument("experiment", help="Experiment ID")
    export_parser.add_argument("--format", choices=["json", "csv", "markdown"], default="json")
    export_parser.add_argument("--output", required=True, help="Output file path")

    parsed = parser.parse_args(args)

    if parsed.action == "list":
        return _list_benchmarks()
    elif parsed.action == "run":
        return _run_benchmark(parsed)
    elif parsed.action == "task":
        return _show_task(parsed.task_id)
    elif parsed.action == "results":
        return _show_results()
    elif parsed.action == "compare":
        return _compare_experiments(parsed.experiment_a, parsed.experiment_b)
    elif parsed.action == "export":
        return _export_results(parsed.experiment, parsed.format, parsed.output)
    else:
        parser.print_help()
        return ""


def _list_benchmarks() -> str:
    """List available benchmarks."""
    dataset = get_default_dataset()
    lines = [
        "Available Benchmarks:",
        "",
        f"  {dataset.dataset_id}: {dataset.name} (v{dataset.version})",
        f"    Tasks: {len(dataset.tasks)}",
        f"    Categories: {', '.join(set(t.category.value for t in dataset.tasks))}",
        f"    Difficulties: {', '.join(set(t.difficulty.value for t in dataset.tasks))}",
    ]
    return "\n".join(lines)


def _run_benchmark(args) -> str:
    """Run a benchmark."""
    dataset = get_default_dataset()

    # Filter tasks
    tasks = dataset.tasks
    if args.tasks:
        tasks = [t for t in tasks if t.task_id in args.tasks]
    if args.difficulty:
        tasks = [t for t in tasks if t.difficulty.value == args.difficulty]
    if args.category:
        tasks = [t for t in tasks if t.category.value == args.category]

    if not tasks:
        return "No tasks match the specified filters."

    # Create experiment config
    config = ExperimentConfig(
        name=f"benchmark-{dataset.dataset_id}",
        benchmark_version=dataset.version,
        provider=args.provider,
        model=args.model,
        seed=args.seed,
        repeat_count=args.repeat,
        timeout=args.timeout,
    )

    # Run tasks (simplified - would integrate with actual agent)
    results = []
    for task in tasks:
        for _ in range(args.repeat):
            result = TaskRunResult(
                task_id=task.task_id,
                experiment_id=config.experiment_id,
                status=BenchmarkStatus.COMPLETED,
                success=True,  # Placeholder
                duration_seconds=1.0,
                iterations=1,
                tool_calls=1,
                tokens_used=100,
                score=1.0,
            )
            results.append(result)

    experiment = ExperimentResult(
        config=config,
        run_results=results,
        total_tasks=len(results),
        successful_tasks=sum(1 for r in results if r.success),
        failed_tasks=sum(1 for r in results if not r.success),
    )

    # Generate report
    scorer = create_default_scorer()
    score = scorer.score_experiment(experiment)
    reporter = BenchmarkReporter()

    if args.format == "json":
        report = reporter.generate_json_report(experiment, score)
        output = json.dumps(report, indent=2, default=str)
    elif args.format == "markdown":
        output = reporter.generate_markdown_report(experiment, score)
    else:
        output = reporter.generate_text_report(experiment, score)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        return f"Benchmark complete. Results saved to {args.output}"

    return output


def _show_task(task_id: str) -> str:
    """Show task details."""
    dataset = get_default_dataset()
    task = dataset.get_task_by_id(task_id)

    if not task:
        return f"Task '{task_id}' not found."

    lines = [
        f"Task: {task.task_id}",
        f"Name: {task.name}",
        f"Category: {task.category.value}",
        f"Difficulty: {task.difficulty.value}",
        f"Tier: {task.tier.value}",
        f"Language: {task.language}",
        "",
        "Description:",
        task.description,
        "",
        "Success Criteria:",
    ]
    for criteria in task.success_criteria:
        lines.append(f"  - {criteria}")

    return "\n".join(lines)


def _show_results() -> str:
    """Show recent results."""
    return "No recent benchmark results."


def _compare_experiments(experiment_a: str, experiment_b: str) -> str:
    """Compare two experiments."""
    return f"Comparison between {experiment_a} and {experiment_b} not yet implemented."


def _export_results(experiment: str, format: str, output: str) -> str:
    """Export results."""
    return f"Export of {experiment} to {output} not yet implemented."


def register_command(subparsers):
    """Register the benchmark command with the main CLI."""
    bench_parser = subparsers.add_parser("benchmark", help="Run benchmarks")
    bench_subparsers = bench_parser.add_subparsers(dest="benchmark_action")

    bench_subparsers.add_parser("list", help="List available benchmarks")

    run_parser = bench_subparsers.add_parser("run", help="Run a benchmark")
    run_parser.add_argument("benchmark_name", nargs="?", default="engineering-v1.0")
    run_parser.add_argument("--provider", default="")
    run_parser.add_argument("--model", default="")
    run_parser.add_argument("--repeat", type=int, default=1)
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    run_parser.add_argument("--output", default="")
    run_parser.add_argument("--ci", action="store_true")

    return bench_parser
