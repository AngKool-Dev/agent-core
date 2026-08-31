"""Tests for verification engine."""

import pytest
from unittest.mock import MagicMock, patch

from argus.verification import (
    CriterionResult,
    VerificationCriterion,
    VerificationEngine,
    VerificationResult,
    VerificationStatus,
    VerificationSuite,
    create_verification_engine,
)
from argus.verification.evaluators import Evaluators
from argus.verification.test_runner import TestRunner, TestRunResult
from argus.verification.diff_checker import DiffChecker, DiffResult, DiffFileChange


class TestVerificationResult:
    def test_passed_result(self):
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            criteria=[CriterionResult(name="test", status=VerificationStatus.PASSED)],
            confidence=1.0,
        )
        assert result.passed is True
        assert result.pass_rate == 1.0

    def test_failed_result(self):
        result = VerificationResult(
            status=VerificationStatus.FAILED,
            criteria=[
                CriterionResult(name="test1", status=VerificationStatus.PASSED),
                CriterionResult(name="test2", status=VerificationStatus.FAILED),
            ],
            confidence=0.5,
        )
        assert result.passed is False
        assert len(result.failed_criteria) == 1
        assert len(result.passed_criteria) == 1

    def test_to_dict(self):
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            criteria=[CriterionResult(name="test", status=VerificationStatus.PASSED)],
            confidence=1.0,
        )
        d = result.to_dict()
        assert d["status"] == "passed"
        assert d["confidence"] == 1.0
        assert len(d["criteria"]) == 1

    def test_from_dict(self):
        data = {
            "status": "passed",
            "criteria": [{"name": "test", "status": "passed"}],
            "confidence": 1.0,
        }
        result = VerificationResult.from_dict(data)
        assert result.status == VerificationStatus.PASSED
        assert len(result.criteria) == 1

    def test_all_passed(self):
        criteria = [CriterionResult(name="test", status=VerificationStatus.PASSED)]
        result = VerificationResult.all_passed(criteria)
        assert result.passed is True
        assert result.confidence == 1.0

    def test_with_failures(self):
        criteria = [
            CriterionResult(name="test1", status=VerificationStatus.PASSED),
            CriterionResult(name="test2", status=VerificationStatus.FAILED),
        ]
        result = VerificationResult.with_failures(criteria)
        assert result.passed is False


class TestVerificationCriterion:
    def test_evaluate_with_boolean(self):
        criterion = VerificationCriterion(
            name="test",
            description="Test",
            evaluator=lambda ctx: True,
        )
        result = criterion.evaluate({})
        assert result.passed is True

    def test_evaluate_with_false(self):
        criterion = VerificationCriterion(
            name="test",
            description="Test",
            evaluator=lambda ctx: False,
        )
        result = criterion.evaluate({})
        assert result.passed is False

    def test_evaluate_with_tuple(self):
        criterion = VerificationCriterion(
            name="test",
            description="Test",
            evaluator=lambda ctx: (True, "Custom message"),
        )
        result = criterion.evaluate({})
        assert result.passed is True
        assert result.message == "Custom message"

    def test_evaluate_with_error(self):
        def bad_evaluator(ctx):
            raise ValueError("test error")

        criterion = VerificationCriterion(
            name="test",
            description="Test",
            evaluator=bad_evaluator,
        )
        result = criterion.evaluate({})
        assert result.status == VerificationStatus.ERROR

    def test_evaluate_no_evaluator(self):
        criterion = VerificationCriterion(name="test", description="Test")
        result = criterion.evaluate({})
        assert result.status == VerificationStatus.SKIPPED


class TestVerificationSuite:
    def test_add_criterion(self):
        suite = VerificationSuite(name="test")
        suite.add_criterion(VerificationCriterion(name="c1", description="d1"))
        assert len(suite.criteria) == 1

    def test_evaluate_all(self):
        suite = VerificationSuite(name="test")
        suite.add_criterion(VerificationCriterion(
            name="c1", description="d1", evaluator=lambda ctx: True
        ))
        suite.add_criterion(VerificationCriterion(
            name="c2", description="d2", evaluator=lambda ctx: False
        ))
        results = suite.evaluate({})
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False

    def test_stop_on_first_failure(self):
        suite = VerificationSuite(name="test", stop_on_first_failure=True)
        suite.add_criterion(VerificationCriterion(
            name="c1", description="d1", evaluator=lambda ctx: False
        ))
        suite.add_criterion(VerificationCriterion(
            name="c2", description="d2", evaluator=lambda ctx: True
        ))
        results = suite.evaluate({})
        assert len(results) == 1  # Stopped after first failure

    def test_required_criteria(self):
        suite = VerificationSuite(name="test")
        suite.add_criterion(VerificationCriterion(name="c1", description="d1", required=True))
        suite.add_criterion(VerificationCriterion(name="c2", description="d2", required=False))
        assert len(suite.required_criteria) == 1
        assert len(suite.optional_criteria) == 1


class TestEvaluators:
    def test_run_command_success(self):
        result = Evaluators.run_command("echo hello", name="test")
        assert result.passed is True

    def test_run_command_failure(self):
        result = Evaluators.run_command("exit 1", name="test")
        assert result.passed is False

    def test_run_command_timeout(self):
        result = Evaluators.run_command("sleep 10", timeout=1, name="test")
        assert result.passed is False
        assert "timed out" in result.message.lower()

    def test_check_files_changed(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="file1.py\nfile2.py\n",
                returncode=0,
            )
            result = Evaluators.check_files_changed(max_files=5, project_path=".")
            assert result.passed is True

    def test_check_files_changed_too_many(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="f1.py\nf2.py\nf3.py\n",
                returncode=0,
            )
            result = Evaluators.check_files_changed(max_files=2, project_path=".")
            assert result.passed is False


class TestTestRunner:
    def test_run_success(self):
        runner = TestRunner()
        result = runner.run("echo hello")
        assert result.success is True

    def test_run_failure(self):
        runner = TestRunner()
        result = runner.run("exit 1")
        assert result.success is False

    def test_run_timeout(self):
        runner = TestRunner()
        result = runner.run("sleep 10", timeout=1)
        assert result.success is False

    def test_to_criterion_result_passed(self):
        runner = TestRunner()
        test_result = TestRunResult(
            command="pytest",
            success=True,
            return_code=0,
            pass_count=5,
            fail_count=0,
        )
        criterion = runner.to_criterion_result(test_result)
        assert criterion.passed is True

    def test_to_criterion_result_failed(self):
        runner = TestRunner()
        test_result = TestRunResult(
            command="pytest",
            success=False,
            return_code=1,
            pass_count=3,
            fail_count=2,
        )
        criterion = runner.to_criterion_result(test_result)
        assert criterion.passed is False


class TestDiffChecker:
    def test_get_diff(self):
        checker = DiffChecker()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="10\t5\tfile1.py\n3\t2\tfile2.py\n",
                returncode=0,
            )
            result = checker.get_diff(project_path=".")
            assert result.total_files == 2
            assert result.total_additions == 13
            assert result.total_deletions == 7

    def test_check_max_files_passed(self):
        checker = DiffChecker()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="10\t5\tfile1.py\n",
                returncode=0,
            )
            result = checker.check_max_files(max_files=5, project_path=".")
            assert result.passed is True

    def test_check_max_files_failed(self):
        checker = DiffChecker()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="1\t1\tf1.py\n1\t1\tf2.py\n1\t1\tf3.py\n",
                returncode=0,
            )
            result = checker.check_max_files(max_files=2, project_path=".")
            assert result.passed is False

    def test_get_changed_files(self):
        checker = DiffChecker()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="10\t5\tfile1.py\n3\t2\tfile2.py\n",
                returncode=0,
            )
            files = checker.get_changed_files(project_path=".")
            assert files == ["file1.py", "file2.py"]


class TestVerificationEngine:
    def test_create_engine(self):
        engine = create_verification_engine(".")
        assert engine is not None

    def test_register_suite(self):
        engine = create_verification_engine(".")
        suite = VerificationSuite(name="test_suite")
        engine.register_suite(suite)
        assert "test_suite" in engine._suites

    def test_verify_with_suite(self):
        engine = create_verification_engine(".")
        suite = VerificationSuite(name="test_suite")
        suite.add_criterion(VerificationCriterion(
            name="test",
            description="Test",
            evaluator=lambda ctx: True,
        ))
        engine.register_suite(suite)
        result = engine.verify("test task", suite_name="test_suite")
        assert result.passed is True

    def test_verify_with_failure(self):
        engine = create_verification_engine(".")
        suite = VerificationSuite(name="test_suite")
        suite.add_criterion(VerificationCriterion(
            name="test",
            description="Test",
            evaluator=lambda ctx: False,
        ))
        engine.register_suite(suite)
        result = engine.verify("test task", suite_name="test_suite")
        assert result.passed is False

    def test_verify_no_suite(self):
        engine = create_verification_engine(".")
        result = engine.verify("test task")
        # No suites registered, should have empty criteria
        assert isinstance(result, VerificationResult)

    def test_build_default_suite(self):
        engine = create_verification_engine(".")
        suite = engine.build_default_suite()
        assert len(suite.criteria) >= 3

    def test_verify_tests(self):
        engine = create_verification_engine(".")
        result = engine.verify_tests(command="echo hello")
        assert result.passed is True

    def test_verify_syntax(self):
        engine = create_verification_engine(".")
        result = engine.verify_syntax(files=[])
        assert result.passed is True  # No files to check

    def test_comprehensive_verification(self):
        engine = create_verification_engine(".")
        # Mock the test runner to avoid actually running tests
        with patch.object(engine, "verify_tests") as mock_tests:
            mock_tests.return_value = CriterionResult(
                name="tests_pass",
                status=VerificationStatus.PASSED,
            )
            result = engine.run_comprehensive(
                task="test",
                test_command="echo hello",
            )
            assert isinstance(result, VerificationResult)