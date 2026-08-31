"""Verification engine - orchestrates verification of agent results."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.verification.criteria import (
    VerificationCriterion,
    VerificationSuite,
    build_comprehensive_suite,
    build_diff_suite,
    build_lint_suite,
    build_test_suite,
    build_type_check_suite,
)
from argus.verification.diff_checker import DiffChecker
from argus.verification.evaluators import Evaluators
from argus.verification.result import (
    CriterionResult,
    VerificationResult,
    VerificationStatus,
)
from argus.verification.test_runner import TestRunner


class VerificationEngine:
    """Engine for verifying agent task results."""

    def __init__(
        self,
        project_path: str = ".",
        test_runner: Optional[TestRunner] = None,
        diff_checker: Optional[DiffChecker] = None,
    ):
        self._project_path = project_path
        self._test_runner = test_runner or TestRunner()
        self._diff_checker = diff_checker or DiffChecker()
        self._suites: Dict[str, VerificationSuite] = {}

    def register_suite(self, suite: VerificationSuite) -> None:
        """Register a verification suite."""
        self._suites[suite.name] = suite

    def verify(
        self,
        task: str,
        context: Dict[str, Any] = None,
        suite_name: Optional[str] = None,
    ) -> VerificationResult:
        """Run verification for a task."""
        start = time.time()
        context = context or {}
        context.setdefault("project_path", self._project_path)
        context.setdefault("task", task)

        if suite_name:
            suite = self._suites.get(suite_name)
            if not suite:
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    message=f"Suite not found: {suite_name}",
                    duration=time.time() - start,
                )
            criteria = suite.evaluate(context)
        else:
            # Run all registered suites
            criteria = []
            for suite in self._suites.values():
                criteria.extend(suite.evaluate(context))

        # Build result
        has_failure = any(c.status == VerificationStatus.FAILED for c in criteria)
        has_error = any(c.status == VerificationStatus.ERROR for c in criteria)
        all_passed = all(c.passed for c in criteria)

        if has_error:
            status = VerificationStatus.ERROR
        elif has_failure:
            status = VerificationStatus.FAILED
        elif all_passed:
            status = VerificationStatus.PASSED
        else:
            status = VerificationStatus.PARTIAL

        confidence = sum(1 for c in criteria if c.passed) / len(criteria) if criteria else 0.0

        return VerificationResult(
            status=status,
            criteria=criteria,
            confidence=confidence,
            message=f"Verification {status.value}: {sum(1 for c in criteria if c.passed)}/{len(criteria)} passed",
            duration=time.time() - start,
            metadata={"task": task, "suite": suite_name or "all"},
        )

    def verify_tests(
        self,
        command: str = "pytest",
        timeout: int = 120,
    ) -> CriterionResult:
        """Verify tests pass."""
        result = self._test_runner.run(command, cwd=self._project_path, timeout=timeout)
        return self._test_runner.to_criterion_result(result)

    def verify_diff(
        self,
        max_files: int = 10,
        max_lines: int = 500,
    ) -> List[CriterionResult]:
        """Verify diff is focused."""
        results = []
        results.append(self._diff_checker.check_max_files(max_files, self._project_path))
        results.append(self._diff_checker.check_max_lines(max_lines, self._project_path))
        return results

    def verify_no_debug_statements(self, files: Optional[List[str]] = None) -> CriterionResult:
        """Verify no debug statements in changed files."""
        if files is None:
            files = self._diff_checker.get_changed_files(self._project_path)
        return Evaluators.check_no_debug_statements(files, self._project_path)

    def verify_syntax(self, files: Optional[List[str]] = None) -> CriterionResult:
        """Verify Python syntax is valid."""
        if files is None:
            files = self._diff_checker.get_changed_files(self._project_path)
        return Evaluators.check_imports_valid(files, self._project_path)

    def verify_type_check(self, command: str = "mypy .") -> CriterionResult:
        """Verify type checks pass."""
        return Evaluators.run_command(command, cwd=self._project_path, name="type_check")

    def verify_lint(self, command: str = "ruff check .") -> CriterionResult:
        """Verify linting passes."""
        return Evaluators.run_command(command, cwd=self._project_path, name="lint_check")

    def build_default_suite(
        self,
        test_command: str = "pytest",
        type_command: str = "mypy .",
        lint_command: str = "ruff check .",
        max_files: int = 10,
        max_lines: int = 500,
    ) -> VerificationSuite:
        """Build a default verification suite."""
        suite = VerificationSuite(name="default", description="Default verification suite")

        # Test execution
        suite.add_criterion(VerificationCriterion(
            name="tests_pass",
            description=f"Run {test_command}",
            evaluator=Evaluators.make_test_evaluator(test_command, self._project_path),
            required=True,
        ))

        # Type check
        suite.add_criterion(VerificationCriterion(
            name="type_check",
            description=f"Run {type_command}",
            evaluator=Evaluators.make_type_check_evaluator(type_command, self._project_path),
            required=False,
        ))

        # Lint check
        suite.add_criterion(VerificationCriterion(
            name="lint_check",
            description=f"Run {lint_command}",
            evaluator=Evaluators.make_lint_evaluator(lint_command, self._project_path),
            required=False,
        ))

        # Diff size
        suite.add_criterion(VerificationCriterion(
            name="focused_changes",
            description=f"Max {max_files} files changed",
            evaluator=Evaluators.make_diff_evaluator(max_files, self._project_path),
            required=True,
        ))

        return suite

    def run_comprehensive(
        self,
        task: str,
        test_command: str = "pytest",
        type_command: str = "mypy .",
        lint_command: str = "ruff check .",
        max_files: int = 10,
        max_lines: int = 500,
    ) -> VerificationResult:
        """Run comprehensive verification."""
        suite = self.build_default_suite(
            test_command=test_command,
            type_command=type_command,
            lint_command=lint_command,
            max_files=max_files,
            max_lines=max_lines,
        )
        self.register_suite(suite)
        return self.verify(task, suite_name="default")


def create_verification_engine(project_path: str = ".") -> VerificationEngine:
    """Create a verification engine with default configuration."""
    engine = VerificationEngine(project_path=project_path)
    return engine