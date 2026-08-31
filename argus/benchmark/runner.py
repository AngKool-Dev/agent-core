"""Benchmark runner that integrates with Phase 19 harness."""

from typing import Callable, Dict, List, Optional

from argus.benchmark.models import (
    BenchmarkStatus,
    ExperimentConfig,
    ExperimentResult,
    TaskRunResult,
)
from argus.harness.models import BenchmarkTask as Phase19Task
from argus.harness.runner import BenchmarkRunner as Phase19Runner
from argus.harness.tasks import get_benchmark_tasks


class HarnessIntegration:
    """
    Integrates Phase 19 harness with Phase 24 benchmark system.

    Allows running Phase 19 tasks through the Phase 24 evaluation framework.
    """

    def __init__(self, phase19_runner: Optional[Phase19Runner] = None):
        self._phase19_runner = phase19_runner or Phase19Runner()

    def run_phase19_tasks(
        self,
        config: ExperimentConfig,
        task_ids: Optional[List[str]] = None,
    ) -> ExperimentResult:
        """Run Phase 19 tasks through Phase 24 evaluation."""
        # Get Phase 19 tasks
        if task_ids:
            tasks = []
            for tid in task_ids:
                task = self._get_phase19_task(tid)
                if task:
                    tasks.append(task)
        else:
            tasks = get_benchmark_tasks()

        # Run tasks
        results = []
        for task in tasks:
            for _ in range(config.repeat_count):
                result = self._run_single_task(task, config)
                results.append(result)

        return ExperimentResult(
            config=config,
            run_results=results,
            total_tasks=len(results),
            successful_tasks=sum(1 for r in results if r.success),
            failed_tasks=sum(1 for r in results if not r.success),
            total_duration=sum(r.duration_seconds for r in results),
            total_iterations=sum(r.iterations for r in results),
            total_tool_calls=sum(r.tool_calls for r in results),
        )

    def _get_phase19_task(self, task_id: str) -> Optional[Phase19Task]:
        """Get a Phase 19 task by ID."""
        from argus.harness.tasks import get_task_by_id
        return get_task_by_id(task_id)

    def _run_single_task(
        self,
        task: Phase19Task,
        config: ExperimentConfig,
    ) -> TaskRunResult:
        """Run a single Phase 19 task and convert to Phase 24 result."""
        try:
            phase19_result = self._phase19_runner.run_task(task)
            return self._convert_result(phase19_result, config)
        except Exception as e:
            return TaskRunResult(
                task_id=task.task_id,
                experiment_id=config.experiment_id,
                status=BenchmarkStatus.ERROR,
                success=False,
                error=str(e),
            )

    def _convert_result(self, phase19_result, config: ExperimentConfig) -> TaskRunResult:
        """Convert Phase 19 TaskResult to Phase 24 TaskRunResult."""
        status_map = {
            "completed": BenchmarkStatus.COMPLETED,
            "failed": BenchmarkStatus.FAILED,
            "error": BenchmarkStatus.ERROR,
            "timeout": BenchmarkStatus.TIMED_OUT,
        }

        return TaskRunResult(
            run_id=phase19_result.run_id,
            task_id=phase19_result.task_id,
            experiment_id=config.experiment_id,
            status=status_map.get(phase19_result.status, BenchmarkStatus.ERROR),
            success=phase19_result.success,
            duration_seconds=phase19_result.duration_seconds,
            iterations=phase19_result.iterations,
            tool_calls=phase19_result.tool_calls,
            model_calls=phase19_result.model_calls,
            tokens_used=phase19_result.tokens_used,
            files_modified=phase19_result.files_modified,
            files_created=phase19_result.files_created,
            files_deleted=phase19_result.files_deleted,
            tests_passed=phase19_result.tests_passed,
            tests_failed=phase19_result.tests_failed,
            verification_passed=phase19_result.verification_passed,
            review_passed=phase19_result.review_passed,
            recovery_attempts=phase19_result.recovery_attempts,
            security_blocks=phase19_result.security_blocks,
            score=phase19_result.score,
            findings=phase19_result.findings,
            error=phase19_result.error,
        )
