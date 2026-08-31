"""Tests for ARGUS Real-World Task Harness."""

import os
import tempfile
from pathlib import Path

import pytest

from argus.harness import (
    BenchmarkRunner,
    BenchmarkScorecard,
    BenchmarkTask,
    SuccessCriteria,
    TaskCategory,
    TaskConstraints,
    TaskDifficulty,
    TaskEnvironment,
    TaskLanguage,
    TaskResult,
    TaskState,
    TaskVerifier,
    get_benchmark_tasks,
    get_task_by_id,
    get_tasks_by_category,
    get_tasks_by_difficulty,
)


class TestTaskModels:
    """Tests for task definition models."""

    def test_create_benchmark_task(self):
        task = BenchmarkTask(
            task_id="test_01",
            name="Test Task",
            description="A test task",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={"test.py": "print('hello')"}),
            success_criteria=SuccessCriteria(
                expected_files_modified=["test.py"],
            ),
        )
        assert task.task_id == "test_01"
        assert task.category == TaskCategory.FIX_FAILING_TEST
        assert task.fingerprint is not None

    def test_task_to_dict(self):
        task = BenchmarkTask(
            task_id="test_02",
            name="Test Task 2",
            description="Another test",
            category=TaskCategory.ADD_FEATURE,
            difficulty=TaskDifficulty.MEDIUM,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={}),
            success_criteria=SuccessCriteria(),
        )
        d = task.to_dict()
        assert d["task_id"] == "test_02"
        assert d["category"] == "add_feature"

    def test_task_from_dict(self):
        task = BenchmarkTask(
            task_id="test_03",
            name="Test Task 3",
            description="Round trip test",
            category=TaskCategory.REFACTOR_MODULE,
            difficulty=TaskDifficulty.HARD,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={"a.py": "x = 1"}),
            success_criteria=SuccessCriteria(
                expected_content_contains={"a.py": ["x = 2"]},
            ),
        )
        d = task.to_dict()
        restored = BenchmarkTask.from_dict(d)
        assert restored.task_id == task.task_id
        assert restored.name == task.name
        assert restored.initial_state.files == task.initial_state.files


class TestTaskRepository:
    """Tests for the task repository."""

    def test_get_all_tasks(self):
        tasks = get_benchmark_tasks()
        assert len(tasks) > 0

    def test_get_task_by_id(self):
        task = get_task_by_id("fix_failing_test_01")
        assert task is not None
        assert task.task_id == "fix_failing_test_01"

    def test_get_nonexistent_task(self):
        task = get_task_by_id("nonexistent_task")
        assert task is None

    def test_get_tasks_by_category(self):
        tasks = get_tasks_by_category(TaskCategory.FIX_FAILING_TEST)
        assert len(tasks) > 0
        assert all(t.category == TaskCategory.FIX_FAILING_TEST for t in tasks)

    def test_get_tasks_by_difficulty(self):
        tasks = get_tasks_by_difficulty(TaskDifficulty.EASY)
        assert len(tasks) > 0
        assert all(t.difficulty == TaskDifficulty.EASY for t in tasks)

    def test_task_categories_covered(self):
        tasks = get_benchmark_tasks()
        categories = set(t.category for t in tasks)
        assert TaskCategory.FIX_FAILING_TEST in categories
        assert TaskCategory.ADD_FEATURE in categories
        assert TaskCategory.REFACTOR_MODULE in categories


class TestTaskEnvironment:
    """Tests for the task environment."""

    def test_setup_creates_files(self):
        task = BenchmarkTask(
            task_id="env_test",
            name="Env Test",
            description="Test environment setup",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "main.py": "print('hello')",
                "sub/foo.py": "x = 1",
            }),
            success_criteria=SuccessCriteria(),
        )
        env = TaskEnvironment(task)
        env.setup()

        assert env.file_exists("main.py")
        assert env.file_exists("sub/foo.py")
        assert env.read_file("main.py") == "print('hello')"
        env.cleanup()

    def test_read_write_file(self):
        task = BenchmarkTask(
            task_id="rw_test",
            name="Read/Write Test",
            description="Test file operations",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={}),
            success_criteria=SuccessCriteria(),
        )
        env = TaskEnvironment(task)
        env.setup()

        env.write_file("test.py", "print('new')")
        assert env.read_file("test.py") == "print('new')"
        env.cleanup()

    def test_get_modified_files(self):
        task = BenchmarkTask(
            task_id="mod_test",
            name="Modified Files Test",
            description="Test modified file detection",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "original.py": "x = 1",
            }),
            success_criteria=SuccessCriteria(),
        )
        env = TaskEnvironment(task)
        env.setup()

        assert env.get_modified_files() == []

        env.write_file("original.py", "x = 2")
        assert "original.py" in env.get_modified_files()
        env.cleanup()

    def test_get_new_files(self):
        task = BenchmarkTask(
            task_id="new_test",
            name="New Files Test",
            description="Test new file detection",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={}),
            success_criteria=SuccessCriteria(),
        )
        env = TaskEnvironment(task)
        env.setup()

        env.write_file("new_file.py", "content")
        assert "new_file.py" in env.get_new_files()
        env.cleanup()

    def test_get_deleted_files(self):
        task = BenchmarkTask(
            task_id="del_test",
            name="Deleted Files Test",
            description="Test deleted file detection",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "to_delete.py": "content",
            }),
            success_criteria=SuccessCriteria(),
        )
        env = TaskEnvironment(task)
        env.setup()

        os.remove(os.path.join(env.get_work_dir(), "to_delete.py"))
        assert "to_delete.py" in env.get_deleted_files()
        env.cleanup()

    def test_run_command(self):
        task = BenchmarkTask(
            task_id="cmd_test",
            name="Command Test",
            description="Test command execution",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={}),
            success_criteria=SuccessCriteria(),
        )
        env = TaskEnvironment(task)
        env.setup()

        returncode, stdout, stderr = env.run_command("echo hello")
        assert returncode == 0
        assert "hello" in stdout
        env.cleanup()


class TestTaskVerifier:
    """Tests for the task verifier."""

    def test_verify_modified_files(self):
        task = BenchmarkTask(
            task_id="verify_mod",
            name="Verify Modified",
            description="Test verification of modified files",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "file.py": "original",
            }),
            success_criteria=SuccessCriteria(
                expected_files_modified=["file.py"],
            ),
        )
        env = TaskEnvironment(task)
        env.setup()
        env.write_file("file.py", "modified")

        verifier = TaskVerifier(task, env)
        passed, findings = verifier.verify()
        assert passed is True
        env.cleanup()

    def test_verify_content_contains(self):
        task = BenchmarkTask(
            task_id="verify_content",
            name="Verify Content",
            description="Test verification of content",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "file.py": "original",
            }),
            success_criteria=SuccessCriteria(
                expected_content_contains={
                    "file.py": ["expected_string"],
                },
            ),
        )
        env = TaskEnvironment(task)
        env.setup()
        env.write_file("file.py", "expected_string is here")

        verifier = TaskVerifier(task, env)
        passed, findings = verifier.verify()
        assert passed is True
        env.cleanup()

    def test_verify_content_not_contains(self):
        task = BenchmarkTask(
            task_id="verify_not_content",
            name="Verify Not Content",
            description="Test verification of content absence",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "file.py": "bad_content original",
            }),
            success_criteria=SuccessCriteria(
                expected_content_not_contains={
                    "file.py": ["bad_content"],
                },
            ),
        )
        env = TaskEnvironment(task)
        env.setup()
        env.write_file("file.py", "good_content")

        verifier = TaskVerifier(task, env)
        passed, findings = verifier.verify()
        assert passed is True
        env.cleanup()

    def test_verify_failure(self):
        task = BenchmarkTask(
            task_id="verify_fail",
            name="Verify Failure",
            description="Test verification failure",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "file.py": "original",
            }),
            success_criteria=SuccessCriteria(
                expected_content_contains={
                    "file.py": ["not_present"],
                },
            ),
        )
        env = TaskEnvironment(task)
        env.setup()

        verifier = TaskVerifier(task, env)
        passed, findings = verifier.verify()
        assert passed is False
        assert len(findings) > 0
        env.cleanup()

    def test_calculate_score(self):
        task = BenchmarkTask(
            task_id="score_test",
            name="Score Test",
            description="Test score calculation",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "file.py": "original",
            }),
            success_criteria=SuccessCriteria(
                expected_content_contains={
                    "file.py": ["a", "b", "c"],
                },
            ),
        )
        env = TaskEnvironment(task)
        env.setup()
        env.write_file("file.py", "a b")  # 2 out of 3

        verifier = TaskVerifier(task, env)
        score = verifier.calculate_score()
        assert 0.0 <= score <= 1.0
        assert score == 2 / 3
        env.cleanup()


class TestBenchmarkRunner:
    """Tests for the benchmark runner."""

    def test_run_task_without_agent(self):
        """Test running a task without an agent (manual verification)."""
        task = BenchmarkTask(
            task_id="manual_test",
            name="Manual Test",
            description="Test without agent",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={
                "file.py": "original",
            }),
            success_criteria=SuccessCriteria(
                expected_files_modified=["file.py"],
            ),
        )
        runner = BenchmarkRunner()
        result = runner.run_task(task)

        assert result.task_id == "manual_test"
        assert result.run_id is not None
        assert result.status in ("completed", "failed", "error")

    def test_run_benchmark_suite(self):
        """Test running a small benchmark suite."""
        tasks = [
            BenchmarkTask(
                task_id=f"bench_{i}",
                name=f"Benchmark Task {i}",
                description=f"Task {i}",
                category=TaskCategory.FIX_FAILING_TEST,
                difficulty=TaskDifficulty.EASY,
                language=TaskLanguage.PYTHON,
                initial_state=TaskState(files={"file.py": "original"}),
                success_criteria=SuccessCriteria(),
            )
            for i in range(3)
        ]

        runner = BenchmarkRunner()
        scorecard = runner.run_benchmark(tasks)

        assert scorecard.total_tasks == 3
        assert len(scorecard.task_results) == 3
        assert scorecard.run_id is not None

    def test_scorecard_calculations(self):
        """Test scorecard metric calculations."""
        scorecard = BenchmarkScorecard(run_id="test_scorecard", total_tasks=4)
        scorecard.completed = 3
        scorecard.failed = 1
        scorecard.total_duration = 10.0
        scorecard.total_iterations = 20
        scorecard.total_tool_calls = 50

        assert scorecard.success_rate == 0.75
        assert scorecard.average_duration == 2.5
        assert scorecard.average_iterations == 5.0
        assert scorecard.average_tool_calls == 12.5

    def test_scorecard_summary(self):
        """Test scorecard summary generation."""
        scorecard = BenchmarkScorecard(run_id="test_summary", total_tasks=2)
        scorecard.completed = 2
        scorecard.total_duration = 5.0

        summary = scorecard.summary()
        assert "ARGUS SCORECARD" in summary
        assert "Success Rate: 100.0%" in summary


class TestBenchmarkScorecard:
    """Tests for benchmark scorecard."""

    def test_empty_scorecard(self):
        scorecard = BenchmarkScorecard(run_id="empty")
        assert scorecard.success_rate == 0.0
        assert scorecard.average_score == 0.0

    def test_scorecard_to_dict(self):
        scorecard = BenchmarkScorecard(run_id="dict_test", total_tasks=1)
        scorecard.completed = 1
        d = scorecard.to_dict()
        assert d["run_id"] == "dict_test"
        assert d["total_tasks"] == 1
        assert d["success_rate"] == 1.0

    def test_verification_pass_rate(self):
        scorecard = BenchmarkScorecard(run_id="verify_rate", total_tasks=2)
        scorecard.task_results = [
            TaskResult(task_id="t1", run_id="r1", success=True, status="completed", verification_passed=True, duration_seconds=1.0),
            TaskResult(task_id="t2", run_id="r2", success=False, status="failed", verification_passed=False, duration_seconds=1.0),
        ]
        assert scorecard.verification_pass_rate == 0.5

    def test_recovery_rate(self):
        scorecard = BenchmarkScorecard(run_id="recovery_rate", total_tasks=2)
        scorecard.task_results = [
            TaskResult(task_id="t1", run_id="r1", success=True, status="completed", recovery_attempts=2, duration_seconds=1.0),
            TaskResult(task_id="t2", run_id="r2", success=False, status="failed", recovery_attempts=1, duration_seconds=1.0),
        ]
        assert scorecard.recovery_rate == 0.5
