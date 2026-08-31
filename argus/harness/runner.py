"""ARGUS Real-World Task Harness - benchmark runner."""

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from argus.harness.models import (
    BenchmarkScorecard,
    BenchmarkTask,
    TaskResult,
)


class TaskEnvironment:
    """Isolated environment for running a task."""

    def __init__(self, task: BenchmarkTask, base_dir: Optional[str] = None):
        self.task = task
        self.base_dir = base_dir or tempfile.mkdtemp(prefix=f"argus_task_{task.task_id}_")
        self.work_dir = os.path.join(self.base_dir, "workspace")
        self._created_files: List[str] = []

    def setup(self) -> None:
        """Set up the task environment."""
        os.makedirs(self.work_dir, exist_ok=True)

        # Write initial state files
        for file_path, content in self.task.initial_state.files.items():
            full_path = os.path.join(self.work_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            self._created_files.append(file_path)

    def cleanup(self) -> None:
        """Clean up the task environment."""
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def get_work_dir(self) -> str:
        """Get the working directory."""
        return self.work_dir

    def read_file(self, file_path: str) -> Optional[str]:
        """Read a file from the workspace."""
        full_path = os.path.join(self.work_dir, file_path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "r") as f:
            return f.read()

    def write_file(self, file_path: str, content: str) -> None:
        """Write a file to the workspace."""
        full_path = os.path.join(self.work_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.join(self.work_dir, file_path))

    def list_files(self) -> List[str]:
        """List all files in the workspace."""
        result = []
        for root, _, files in os.walk(self.work_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, self.work_dir)
                result.append(rel)
        return result

    def get_modified_files(self) -> List[str]:
        """Get list of files that were modified after setup."""
        modified = []
        for file_path in self.task.initial_state.files:
            current = self.read_file(file_path)
            if current is not None:
                original = self.task.initial_state.files[file_path]
                if current != original:
                    modified.append(file_path)
        return modified

    def get_new_files(self) -> List[str]:
        """Get list of files that were created after setup."""
        current_files = set(self.list_files())
        original_files = set(self.task.initial_state.files.keys())
        return list(current_files - original_files)

    def get_deleted_files(self) -> List[str]:
        """Get list of files that were deleted after setup."""
        original_files = set(self.task.initial_state.files.keys())
        current_files = set(self.list_files())
        return list(original_files - current_files)

    def run_command(self, command: str, timeout: int = 30) -> tuple:
        """Run a shell command in the workspace."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


class TaskVerifier:
    """Verifies task success criteria."""

    def __init__(self, task: BenchmarkTask, environment: TaskEnvironment):
        self.task = task
        self.env = environment

    def verify(self) -> tuple:
        """Verify all success criteria. Returns (passed, findings)."""
        findings = []
        passed = True

        criteria = self.task.success_criteria

        # Check expected modified files
        if criteria.expected_files_modified:
            modified = self.env.get_modified_files()
            for expected in criteria.expected_files_modified:
                if expected not in modified:
                    findings.append(f"Expected file not modified: {expected}")
                    passed = False

        # Check expected created files
        if criteria.expected_files_created:
            new_files = self.env.get_new_files()
            for expected in criteria.expected_files_created:
                if expected not in new_files:
                    findings.append(f"Expected file not created: {expected}")
                    passed = False

        # Check expected deleted files
        if criteria.expected_files_deleted:
            deleted = self.env.get_deleted_files()
            for expected in criteria.expected_files_deleted:
                if expected not in deleted:
                    findings.append(f"Expected file not deleted: {expected}")
                    passed = False

        # Check content contains
        if criteria.expected_content_contains:
            for file_path, expected_strings in criteria.expected_content_contains.items():
                content = self.env.read_file(file_path)
                if content is None:
                    findings.append(f"File not found for content check: {file_path}")
                    passed = False
                    continue
                for expected in expected_strings:
                    if expected not in content:
                        findings.append(f"Expected content not found in {file_path}: {expected}")
                        passed = False

        # Check content not contains
        if criteria.expected_content_not_contains:
            for file_path, unexpected_strings in criteria.expected_content_not_contains.items():
                content = self.env.read_file(file_path)
                if content is None:
                    continue
                for unexpected in unexpected_strings:
                    if unexpected in content:
                        findings.append(f"Unexpected content found in {file_path}: {unexpected}")
                        passed = False

        # Check tests pass
        if criteria.expected_tests_pass:
            for test in criteria.expected_tests_pass:
                test_passed = self._run_test(test)
                if not test_passed:
                    findings.append(f"Test failed: {test}")
                    passed = False

        # Check tests fail
        if criteria.expected_tests_fail:
            for test in criteria.expected_tests_fail:
                test_passed = self._run_test(test)
                if test_passed:
                    findings.append(f"Test unexpectedly passed: {test}")
                    passed = False

        # Check exit code
        if criteria.expected_exit_code is not None:
            # This would be set by the agent execution
            pass

        # Check output contains
        if criteria.expected_output_contains:
            # This would be set by the agent execution
            pass

        return passed, findings

    def _run_test(self, test: str) -> bool:
        """Run a specific test."""
        returncode, stdout, stderr = self.env.run_command(
            f"python -m pytest {test} -v --tb=short 2>&1",
            timeout=30,
        )
        return returncode == 0

    def calculate_score(self) -> float:
        """Calculate a score from 0.0 to 1.0 based on criteria met."""
        passed, findings = self.verify()
        if passed:
            return 1.0

        criteria = self.task.success_criteria
        total_checks = 0
        passed_checks = 0

        if criteria.expected_files_modified:
            total_checks += len(criteria.expected_files_modified)
            modified = self.env.get_modified_files()
            passed_checks += sum(1 for f in criteria.expected_files_modified if f in modified)

        if criteria.expected_content_contains:
            for file_path, expected_strings in criteria.expected_content_contains.items():
                total_checks += len(expected_strings)
                content = self.env.read_file(file_path)
                if content:
                    passed_checks += sum(1 for s in expected_strings if s in content)

        if criteria.expected_tests_pass:
            total_checks += len(criteria.expected_tests_pass)
            for test in criteria.expected_tests_pass:
                if self._run_test(test):
                    passed_checks += 1

        if total_checks == 0:
            return 1.0 if passed else 0.0

        return passed_checks / total_checks


class BenchmarkRunner:
    """Runs benchmark tasks and collects results."""

    def __init__(self, agent_factory: Optional[Callable] = None):
        self.agent_factory = agent_factory
        self._custom_checks: Dict[str, Callable] = {}

    def register_custom_check(self, name: str, check_fn: Callable) -> None:
        """Register a custom check function."""
        self._custom_checks[name] = check_fn

    def run_task(self, task: BenchmarkTask) -> TaskResult:
        """Run a single benchmark task."""
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        env = TaskEnvironment(task)
        result = TaskResult(
            task_id=task.task_id,
            run_id=run_id,
            success=False,
            status="running",
            started_at=start_time,
            duration_seconds=0.0,
        )

        try:
            env.setup()

            # Run the agent
            if self.agent_factory:
                agent = self.agent_factory(env.get_work_dir())
                agent_result = agent.execute(task.description)
                result.iterations = agent_result.get("iterations", 0)
                result.tool_calls = agent_result.get("tools_used", 0)
                result.output = agent_result.get("final_response", "")

            # Verify the result
            verifier = TaskVerifier(task, env)
            passed, findings = verifier.verify()
            result.verification_passed = passed
            result.findings = findings
            result.score = verifier.calculate_score()

            # Collect file changes
            result.files_modified = env.get_modified_files()
            result.files_created = env.get_new_files()
            result.files_deleted = env.get_deleted_files()

            # Run tests
            if task.success_criteria.expected_tests_pass:
                for test in task.success_criteria.expected_tests_pass:
                    if verifier._run_test(test):
                        result.tests_passed.append(test)
                    else:
                        result.tests_failed.append(test)

            # Determine success
            result.success = passed and result.score >= 0.8
            result.status = "completed" if result.success else "failed"

        except TimeoutError:
            result.status = "timeout"
            result.error = f"Task timed out after {task.timeout_seconds}s"
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        finally:
            result.duration_seconds = time.time() - start_time
            result.completed_at = time.time()
            env.cleanup()

        return result

    def run_benchmark(self, tasks: List[BenchmarkTask]) -> BenchmarkScorecard:
        """Run a full benchmark suite."""
        run_id = f"benchmark-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        scorecard = BenchmarkScorecard(
            run_id=run_id,
            total_tasks=len(tasks),
            started_at=start_time,
        )

        for task in tasks:
            task_result = self.run_task(task)
            scorecard.task_results.append(task_result)

            if task_result.status == "completed":
                scorecard.completed += 1
            elif task_result.status == "failed":
                scorecard.failed += 1
            elif task_result.status == "timeout":
                scorecard.timed_out += 1
            elif task_result.status == "error":
                scorecard.errors += 1

            scorecard.total_duration += task_result.duration_seconds
            scorecard.total_iterations += task_result.iterations
            scorecard.total_tool_calls += task_result.tool_calls
            scorecard.total_model_calls += task_result.model_calls
            scorecard.total_tokens += task_result.tokens_used
            scorecard.total_recovery_attempts += task_result.recovery_attempts
            scorecard.total_security_blocks += task_result.security_blocks

        scorecard.completed_at = time.time()
        return scorecard

    def run_task_with_replay(self, task: BenchmarkTask) -> tuple:
        """Run a single benchmark task with replay capture.

        Returns:
            Tuple of (TaskResult, ReplayRun, ForensicReport)
        """
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        env = TaskEnvironment(task)
        result = TaskResult(
            task_id=task.task_id,
            run_id=run_id,
            success=False,
            status="running",
            started_at=start_time,
            duration_seconds=0.0,
        )

        try:
            env.setup()

            # Run the agent
            if self.agent_factory:
                agent = self.agent_factory(env.get_work_dir())
                agent_result = agent.execute(task.description)
                result.iterations = agent_result.get("iterations", 0)
                result.tool_calls = agent_result.get("tools_used", 0)
                result.output = agent_result.get("final_response", "")

            # Verify the result
            verifier = TaskVerifier(task, env)
            passed, findings = verifier.verify()
            result.verification_passed = passed
            result.findings = findings
            result.score = verifier.calculate_score()

            # Collect file changes
            result.files_modified = env.get_modified_files()
            result.files_created = env.get_new_files()
            result.files_deleted = env.get_deleted_files()

            # Run tests
            if task.success_criteria.expected_tests_pass:
                for test in task.success_criteria.expected_tests_pass:
                    if verifier._run_test(test):
                        result.tests_passed.append(test)
                    else:
                        result.tests_failed.append(test)

            # Determine success
            result.success = passed and result.score >= 0.8
            result.status = "completed" if result.success else "failed"

        except TimeoutError:
            result.status = "timeout"
            result.error = f"Task timed out after {task.timeout_seconds}s"
        except Exception as e:
            result.status = "error"
            result.error = str(e)
        finally:
            result.duration_seconds = time.time() - start_time
            result.completed_at = time.time()

        # Capture replay data
        replay_run = self._capture_replay_data(run_id, task, result)
        forensic_report = self._generate_forensic_report(replay_run)

        env.cleanup()
        return result, replay_run, forensic_report

    def _capture_replay_data(self, run_id: str, task: BenchmarkTask, result: TaskResult):
        """Capture replay data from the event system."""
        try:
            from argus.replay import ReplayRun, ReplayEvent, RunStatus
            from argus.events import get_correlation_tracker

            tracker = get_correlation_tracker()
            events = tracker.get_run_events(run_id)

            replay_events = []
            for i, event in enumerate(events):
                replay_event = ReplayEvent(
                    sequence=i,
                    event_id=event.event_id,
                    timestamp=event.timestamp,
                    event_type=event.event_type.value,
                    category=event.category,
                    source=event.source.value,
                    run_id=event.run_id,
                    session_id=event.session_id,
                    operation_id=event.operation_id,
                    attempt_id=event.attempt_id,
                    parent_id=event.parent_event_id,
                    payload=dict(event.payload),
                    status=event.status.value if event.status else None,
                    capability=event.capability,
                    duration=event.duration,
                    metadata=dict(event.metadata),
                )
                replay_events.append(replay_event)

            status = RunStatus.COMPLETE if result.success else RunStatus.PARTIAL
            if result.status == "error":
                status = RunStatus.CORRUPTED

            return ReplayRun(
                run_id=run_id,
                task=task.description,
                started_at=result.started_at,
                ended_at=result.completed_at,
                status=status,
                events=replay_events,
                metadata={
                    "task_id": task.task_id,
                    "task_name": task.name,
                    "score": result.score,
                    "success": result.success,
                },
            )
        except Exception:
            return None

    def _generate_forensic_report(self, replay_run):
        """Generate a forensic report from replay data."""
        if replay_run is None:
            return None
        try:
            from argus.replay import ForensicReport
            return ForensicReport(replay_run)
        except Exception:
            return None
        """Run a full benchmark suite."""
        run_id = f"benchmark-{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        scorecard = BenchmarkScorecard(
            run_id=run_id,
            total_tasks=len(tasks),
            started_at=start_time,
        )

        for task in tasks:
            task_result = self.run_task(task)
            scorecard.task_results.append(task_result)

            if task_result.status == "completed":
                scorecard.completed += 1
            elif task_result.status == "failed":
                scorecard.failed += 1
            elif task_result.status == "timeout":
                scorecard.timed_out += 1
            elif task_result.status == "error":
                scorecard.errors += 1

            scorecard.total_duration += task_result.duration_seconds
            scorecard.total_iterations += task_result.iterations
            scorecard.total_tool_calls += task_result.tool_calls
            scorecard.total_model_calls += task_result.model_calls
            scorecard.total_tokens += task_result.tokens_used
            scorecard.total_recovery_attempts += task_result.recovery_attempts
            scorecard.total_security_blocks += task_result.security_blocks

        scorecard.completed_at = time.time()
        return scorecard
