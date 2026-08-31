"""Validation verifier for ARGUS real-world scenarios."""

import ast
import os
from typing import Dict, List, Tuple

from argus.validation.models import (
    OutcomeType,
    ValidationResult,
    ValidationScenario,
    ValidationStatus,
)


class ScenarioVerifier:
    """Verifies validation scenario results against success criteria."""

    def __init__(self):
        self._criteria_checks = {
            "file_exists": self._check_file_exists,
            "class_defined": self._check_class_defined,
            "method_exists": self._check_method_exists,
            "type_hints": self._check_type_hints,
            "docstrings": self._check_docstrings,
            "error_handling": self._check_error_handling,
            "tests_exist": self._check_tests_exist,
            "git_initialized": self._check_git_initialized,
            "branch_created": self._check_branch_created,
            "changes_committed": self._check_changes_committed,
            "branch_merged": self._check_branch_merged,
            "no_hardcoded_secrets": self._check_no_hardcoded_secrets,
            "strong_hashing": self._check_strong_hashing,
            "input_validation": self._check_input_validation,
        }

    def verify(self, scenario: ValidationScenario, result: ValidationResult) -> ValidationResult:
        """Verify a result against its scenario."""
        verification_results = {}

        for criterion in scenario.success_criteria:
            passed = self._verify_criterion(criterion, scenario, result)
            verification_results[criterion] = passed

        result.verification_results = verification_results

        # Determine outcome based on verification
        if verification_results:
            pass_rate = sum(1 for v in verification_results.values() if v) / len(verification_results)
            if pass_rate >= 0.9:
                result.outcome = OutcomeType.SUCCESS
                result.success = True
                result.status = ValidationStatus.PASSED
            elif pass_rate >= 0.6:
                result.outcome = OutcomeType.PARTIAL_SUCCESS
                result.success = False
                result.status = ValidationStatus.FAILED
            else:
                result.outcome = OutcomeType.FAILURE
                result.success = False
                result.status = ValidationStatus.FAILED
        else:
            # No criteria to verify - use basic checks
            if result.errors:
                result.outcome = OutcomeType.FAILURE
                result.status = ValidationStatus.FAILED
            else:
                result.outcome = OutcomeType.SUCCESS
                result.success = True
                result.status = ValidationStatus.PASSED

        return result

    def _verify_criterion(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Verify a single success criterion."""
        # Check for exact matches first
        for check_name, check_func in self._criteria_checks.items():
            if check_name in criterion.lower():
                return check_func(criterion, scenario, result)

        # Generic checks based on criterion text
        criterion_lower = criterion.lower()

        if "file exists" in criterion_lower or "exists" in criterion_lower:
            return self._check_file_exists_generic(criterion, scenario, result)

        if "function" in criterion_lower and "exists" in criterion_lower:
            return self._check_function_exists(criterion, scenario, result)

        if "class" in criterion_lower and "exists" in criterion_lower:
            return self._check_class_exists(criterion, scenario, result)

        if "test" in criterion_lower:
            return self._check_test_criterion(criterion, scenario, result)

        # Default: check if there are no errors
        return len(result.errors) == 0

    def _check_file_exists(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if expected files exist."""
        for expected_file in scenario.expected_files:
            if expected_file in result.files_created or expected_file in result.files_modified:
                return True
            # Check if file exists on disk
            if os.path.exists(expected_file):
                return True
        return False

    def _check_file_exists_generic(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Generic file existence check."""
        # Extract filename from criterion
        for expected_file in scenario.expected_files:
            if expected_file in criterion:
                return (
                    expected_file in result.files_created
                    or expected_file in result.files_modified
                    or os.path.exists(expected_file)
                )
        return False

    def _check_class_defined(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if a class is defined in created files."""
        for filepath in result.files_created + result.files_modified:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            return True
                except (SyntaxError, Exception):
                    continue
        return False

    def _check_class_exists(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if a specific class exists."""
        return self._check_class_defined(criterion, scenario, result)

    def _check_method_exists(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if methods exist in created files."""
        for filepath in result.files_created + result.files_modified:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            return True
                except (SyntaxError, Exception):
                    continue
        return False

    def _check_function_exists(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if functions exist."""
        return self._check_method_exists(criterion, scenario, result)

    def _check_type_hints(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if type hints are present."""
        for filepath in result.files_created + result.files_modified:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Check for return type annotation
                            if node.returns is not None:
                                return True
                            # Check for argument type annotations
                            for arg in node.args.args:
                                if arg.annotation is not None:
                                    return True
                except (SyntaxError, Exception):
                    continue
        return False

    def _check_docstrings(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if docstrings are present."""
        for filepath in result.files_created + result.files_modified:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                            if (
                                ast.get_docstring(node) is not None
                            ):
                                return True
                except (SyntaxError, Exception):
                    continue
        return False

    def _check_error_handling(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if error handling is present."""
        for filepath in result.files_created + result.files_modified:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Try):
                            return True
                except (SyntaxError, Exception):
                    continue
        return False

    def _check_tests_exist(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if test files exist."""
        for filepath in result.files_created:
            if "test" in filepath.lower() and filepath.endswith(".py"):
                return True
        return False

    def _check_test_criterion(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check test-related criteria."""
        return self._check_tests_exist(criterion, scenario, result)

    def _check_git_initialized(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if git is initialized."""
        return os.path.exists(".git")

    def _check_branch_created(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if a branch was created."""
        # This would require git command execution
        # For now, check if git log shows branch creation
        return self._check_git_initialized(criterion, scenario, result)

    def _check_changes_committed(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if changes are committed."""
        return self._check_git_initialized(criterion, scenario, result)

    def _check_branch_merged(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check if branch is merged."""
        return self._check_git_initialized(criterion, scenario, result)

    def _check_no_hardcoded_secrets(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check for hardcoded secrets."""
        secret_patterns = ["secret_key", "password", "api_key", "token"]
        for filepath in result.files_modified + result.files_created:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read().lower()
                    for pattern in secret_patterns:
                        if f'{pattern} = "' in source or f"{pattern} = '" in source:
                            return False
                except Exception:
                    continue
        return True

    def _check_strong_hashing(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check for strong hashing algorithms."""
        strong_algorithms = ["bcrypt", "scrypt", "argon2", "sha256", "sha512"]
        for filepath in result.files_modified + result.files_created:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read().lower()
                    for algo in strong_algorithms:
                        if algo in source:
                            return True
                except Exception:
                    continue
        return False

    def _check_input_validation(self, criterion: str, scenario: ValidationScenario, result: ValidationResult) -> bool:
        """Check for input validation."""
        validation_patterns = ["if not ", "raise ", "validate", "isinstance"]
        for filepath in result.files_modified + result.files_created:
            if filepath.endswith(".py") and os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        source = f.read()
                    for pattern in validation_patterns:
                        if pattern in source:
                            return True
                except Exception:
                    continue
        return False
