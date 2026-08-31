"""Verification criteria definitions."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from argus.verification.result import CriterionResult, VerificationStatus


@dataclass
class VerificationCriterion:
    """A single verification criterion."""
    name: str
    description: str
    evaluator: Optional[Callable] = None
    required: bool = True
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, context: Dict[str, Any]) -> CriterionResult:
        """Evaluate this criterion."""
        if self.evaluator is None:
            return CriterionResult(
                name=self.name,
                status=VerificationStatus.SKIPPED,
                message="No evaluator defined",
            )

        import time
        start = time.time()
        try:
            result = self.evaluator(context)
            duration = time.time() - start

            if isinstance(result, CriterionResult):
                result.duration = duration
                return result
            elif isinstance(result, bool):
                return CriterionResult(
                    name=self.name,
                    status=VerificationStatus.PASSED if result else VerificationStatus.FAILED,
                    message=f"{'Passed' if result else 'Failed'}: {self.description}",
                    duration=duration,
                )
            elif isinstance(result, tuple):
                passed, message = result
                return CriterionResult(
                    name=self.name,
                    status=VerificationStatus.PASSED if passed else VerificationStatus.FAILED,
                    message=message,
                    duration=duration,
                )
            else:
                return CriterionResult(
                    name=self.name,
                    status=VerificationStatus.PASSED if result else VerificationStatus.FAILED,
                    message=str(result),
                    duration=duration,
                )
        except Exception as e:
            return CriterionResult(
                name=self.name,
                status=VerificationStatus.ERROR,
                message=f"Evaluation error: {e}",
                duration=time.time() - start,
            )


@dataclass
class VerificationSuite:
    """A suite of verification criteria."""
    name: str
    description: str = ""
    criteria: List[VerificationCriterion] = field(default_factory=list)
    stop_on_first_failure: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_criterion(self, criterion: VerificationCriterion) -> "VerificationSuite":
        self.criteria.append(criterion)
        return self

    def evaluate(self, context: Dict[str, Any]) -> List[CriterionResult]:
        """Evaluate all criteria."""
        results = []
        for criterion in self.criteria:
            result = criterion.evaluate(context)
            results.append(result)
            if self.stop_on_first_failure and result.status == VerificationStatus.FAILED:
                break
        return results

    @property
    def required_criteria(self) -> List[VerificationCriterion]:
        return [c for c in self.criteria if c.required]

    @property
    def optional_criteria(self) -> List[VerificationCriterion]:
        return [c for c in self.criteria if not c.required]


def build_test_suite(test_command: str = "pytest", timeout: int = 120) -> VerificationSuite:
    """Build a standard test verification suite."""
    suite = VerificationSuite(
        name="test_suite",
        description="Run project tests",
    )

    suite.add_criterion(VerificationCriterion(
        name="test_execution",
        description=f"Run {test_command}",
        metadata={"command": test_command, "timeout": timeout},
    ))

    return suite


def build_diff_suite(max_files_changed: int = 10) -> VerificationSuite:
    """Build a diff verification suite."""
    suite = VerificationSuite(
        name="diff_check",
        description="Verify changes are focused",
    )

    suite.add_criterion(VerificationCriterion(
        name="files_changed",
        description=f"Check no more than {max_files_changed} files changed",
        metadata={"max_files": max_files_changed},
    ))

    return suite


def build_type_check_suite(command: str = "mypy") -> VerificationSuite:
    """Build a type checking verification suite."""
    suite = VerificationSuite(
        name="type_check",
        description="Run type checks",
    )

    suite.add_criterion(VerificationCriterion(
        name="type_check",
        description=f"Run {command}",
        metadata={"command": command},
    ))

    return suite


def build_lint_suite(command: str = "ruff check") -> VerificationSuite:
    """Build a linting verification suite."""
    suite = VerificationSuite(
        name="lint_check",
        description="Run linter",
    )

    suite.add_criterion(VerificationCriterion(
        name="lint",
        description=f"Run {command}",
        metadata={"command": command},
    ))

    return suite


def build_comprehensive_suite(
    test_command: str = "pytest",
    type_command: str = "mypy",
    lint_command: str = "ruff check",
    max_files_changed: int = 10,
) -> VerificationSuite:
    """Build a comprehensive verification suite."""
    suite = VerificationSuite(
        name="comprehensive",
        description="Full verification suite",
    )

    suite.add_criterion(VerificationCriterion(
        name="tests_pass",
        description=f"Run {test_command}",
        required=True,
        metadata={"command": test_command},
    ))

    suite.add_criterion(VerificationCriterion(
        name="type_check",
        description=f"Run {type_command}",
        required=False,
        metadata={"command": type_command},
    ))

    suite.add_criterion(VerificationCriterion(
        name="lint_check",
        description=f"Run {lint_command}",
        required=False,
        metadata={"command": lint_command},
    ))

    suite.add_criterion(VerificationCriterion(
        name="focused_changes",
        description=f"Max {max_files_changed} files changed",
        required=True,
        metadata={"max_files": max_files_changed},
    ))

    return suite