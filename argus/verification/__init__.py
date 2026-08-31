"""ARGUS verification subsystem."""

from argus.verification.result import (
    CriterionResult,
    VerificationResult,
    VerificationStatus,
)
from argus.verification.criteria import (
    VerificationCriterion,
    VerificationSuite,
    build_comprehensive_suite,
    build_diff_suite,
    build_lint_suite,
    build_test_suite,
    build_type_check_suite,
)
from argus.verification.evaluators import Evaluators
from argus.verification.test_runner import TestRunner, TestRunResult
from argus.verification.diff_checker import DiffChecker, DiffResult, DiffFileChange
from argus.verification.engine import VerificationEngine, create_verification_engine

__all__ = [
    "CriterionResult",
    "VerificationResult",
    "VerificationStatus",
    "VerificationCriterion",
    "VerificationSuite",
    "build_comprehensive_suite",
    "build_diff_suite",
    "build_lint_suite",
    "build_test_suite",
    "build_type_check_suite",
    "Evaluators",
    "TestRunner",
    "TestRunResult",
    "DiffChecker",
    "DiffResult",
    "DiffFileChange",
    "VerificationEngine",
    "create_verification_engine",
]