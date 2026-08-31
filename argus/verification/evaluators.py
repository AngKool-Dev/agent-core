"""Verification evaluators - concrete checks that can be run."""

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from argus.verification.result import CriterionResult, VerificationStatus


class Evaluators:
    """Collection of verification evaluators."""

    @staticmethod
    def run_command(
        command: str,
        cwd: str = ".",
        timeout: int = 120,
        name: str = "command",
    ) -> CriterionResult:
        """Run a shell command and verify it succeeds."""
        start = time.time()
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - start

            if result.returncode == 0:
                return CriterionResult(
                    name=name,
                    status=VerificationStatus.PASSED,
                    message=f"Command succeeded: {command}",
                    details={"stdout": result.stdout[:1000], "stderr": result.stderr[:500]},
                    duration=duration,
                )
            else:
                return CriterionResult(
                    name=name,
                    status=VerificationStatus.FAILED,
                    message=f"Command failed (exit {result.returncode}): {command}",
                    details={"stdout": result.stdout[:1000], "stderr": result.stderr[:1000]},
                    duration=duration,
                )
        except subprocess.TimeoutExpired:
            return CriterionResult(
                name=name,
                status=VerificationStatus.FAILED,
                message=f"Command timed out after {timeout}s: {command}",
                duration=time.time() - start,
            )
        except Exception as e:
            return CriterionResult(
                name=name,
                status=VerificationStatus.ERROR,
                message=f"Command error: {e}",
                duration=time.time() - start,
            )

    @staticmethod
    def check_files_changed(
        max_files: int = 10,
        project_path: str = ".",
        name: str = "files_changed",
    ) -> CriterionResult:
        """Check that no more than max_files have been changed."""
        start = time.time()
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            changed_files = [f for f in result.stdout.strip().split("\n") if f]
            duration = time.time() - start

            if len(changed_files) <= max_files:
                return CriterionResult(
                    name=name,
                    status=VerificationStatus.PASSED,
                    message=f"{len(changed_files)} files changed (max {max_files})",
                    details={"files": changed_files, "count": len(changed_files)},
                    duration=duration,
                )
            else:
                return CriterionResult(
                    name=name,
                    status=VerificationStatus.FAILED,
                    message=f"{len(changed_files)} files changed (max {max_files})",
                    details={"files": changed_files, "count": len(changed_files)},
                    duration=duration,
                )
        except Exception as e:
            return CriterionResult(
                name=name,
                status=VerificationStatus.ERROR,
                message=f"Failed to check changed files: {e}",
                duration=time.time() - start,
            )

    @staticmethod
    def check_uncommitted_changes(project_path: str = ".") -> CriterionResult:
        """Check for uncommitted changes."""
        start = time.time()
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            changes = [line for line in result.stdout.strip().split("\n") if line.strip()]
            duration = time.time() - start

            if not changes:
                return CriterionResult(
                    name="uncommitted_changes",
                    status=VerificationStatus.PASSED,
                    message="No uncommitted changes",
                    duration=duration,
                )
            else:
                return CriterionResult(
                    name="uncommitted_changes",
                    status=VerificationStatus.FAILED,
                    message=f"{len(changes)} uncommitted changes",
                    details={"changes": changes[:20]},
                    duration=duration,
                )
        except Exception as e:
            return CriterionResult(
                name="uncommitted_changes",
                status=VerificationStatus.ERROR,
                message=f"Failed to check status: {e}",
                duration=time.time() - start,
            )

    @staticmethod
    def check_no_debug_statements(
        files: List[str],
        project_path: str = ".",
        patterns: Optional[List[str]] = None,
    ) -> CriterionResult:
        """Check that files don't contain debug statements."""
        start = time.time()
        if patterns is None:
            patterns = [
                r"^\s*print\s*\(",
                r"^\s*console\.log\s*\(",
                r"^\s*debugger\s*;",
                r"^\s*breakpoint\s*\(",
                r"^\s*import\s+pdb",
                r"^\s*pdb\.set_trace",
            ]

        violations: List[Dict[str, Any]] = []
        for filepath in files:
            full_path = Path(project_path) / filepath
            if not full_path.exists():
                continue
            try:
                content = full_text = full_path.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.split("\n"), 1):
                    for pattern in patterns:
                        if re.search(pattern, line):
                            violations.append({
                                "file": filepath,
                                "line": i,
                                "content": line.strip()[:100],
                                "pattern": pattern,
                            })
            except Exception:
                continue

        duration = time.time() - start
        if not violations:
            return CriterionResult(
                name="no_debug_statements",
                status=VerificationStatus.PASSED,
                message="No debug statements found",
                duration=duration,
            )
        else:
            return CriterionResult(
                name="no_debug_statements",
                status=VerificationStatus.FAILED,
                message=f"{len(violations)} debug statements found",
                details={"violations": violations[:20]},
                duration=duration,
            )

    @staticmethod
    def check_file_exists(filepath: str, project_path: str = ".") -> CriterionResult:
        """Check that a file exists."""
        start = time.time()
        full_path = Path(project_path) / filepath
        duration = time.time() - start

        if full_path.exists():
            return CriterionResult(
                name="file_exists",
                status=VerificationStatus.PASSED,
                message=f"File exists: {filepath}",
                duration=duration,
            )
        else:
            return CriterionResult(
                name="file_exists",
                status=VerificationStatus.FAILED,
                message=f"File not found: {filepath}",
                duration=duration,
            )

    @staticmethod
    def check_file_does_not_contain(
        filepath: str,
        patterns: List[str],
        project_path: str = ".",
    ) -> CriterionResult:
        """Check that a file does not contain certain patterns."""
        start = time.time()
        full_path = Path(project_path) / filepath
        duration = time.time() - start

        if not full_path.exists():
            return CriterionResult(
                name="file_does_not_contain",
                status=VerificationStatus.SKIPPED,
                message=f"File not found: {filepath}",
                duration=duration,
            )

        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            violations = []
            for i, line in enumerate(content.split("\n"), 1):
                for pattern in patterns:
                    if re.search(pattern, line):
                        violations.append({
                            "line": i,
                            "content": line.strip()[:100],
                            "pattern": pattern,
                        })

            if not violations:
                return CriterionResult(
                    name="file_does_not_contain",
                    status=VerificationStatus.PASSED,
                    message=f"No forbidden patterns in {filepath}",
                    duration=duration,
                )
            else:
                return CriterionResult(
                    name="file_does_not_contain",
                    status=VerificationStatus.FAILED,
                    message=f"{len(violations)} forbidden patterns in {filepath}",
                    details={"violations": violations[:10]},
                    duration=duration,
                )
        except Exception as e:
            return CriterionResult(
                name="file_does_not_contain",
                status=VerificationStatus.ERROR,
                message=f"Error reading file: {e}",
                duration=time.time() - start,
            )

    @staticmethod
    def check_test_file_exists(source_filepath: str, project_path: str = ".") -> CriterionResult:
        """Check that a test file exists for a source file."""
        start = time.time()
        path = Path(source_filepath)

        # Common test file patterns
        test_patterns = [
            f"tests/test_{path.name}",
            f"test_{path.name}",
            f"{path.stem}_test.py",
            f"tests/{path.stem}_test.py",
        ]

        for test_pattern in test_patterns:
            if (Path(project_path) / test_pattern).exists():
                return CriterionResult(
                    name="test_file_exists",
                    status=VerificationStatus.PASSED,
                    message=f"Test file found: {test_pattern}",
                    duration=time.time() - start,
                )

        return CriterionResult(
            name="test_file_exists",
            status=VerificationStatus.FAILED,
            message=f"No test file found for {source_filepath}",
            duration=time.time() - start,
        )

    @staticmethod
    def check_imports_valid(files: List[str], project_path: str = ".") -> CriterionResult:
        """Check that Python imports are valid."""
        start = time.time()
        errors = []

        for filepath in files:
            if not filepath.endswith(".py"):
                continue
            full_path = Path(project_path) / filepath
            if not full_path.exists():
                continue
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                # Check for syntax errors
                import ast
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    errors.append({"file": filepath, "error": str(e)})
            except Exception as e:
                errors.append({"file": filepath, "error": str(e)})

        duration = time.time() - start
        if not errors:
            return CriterionResult(
                name="imports_valid",
                status=VerificationStatus.PASSED,
                message="All files have valid syntax",
                duration=duration,
            )
        else:
            return CriterionResult(
                name="imports_valid",
                status=VerificationStatus.FAILED,
                message=f"{len(errors)} files have syntax errors",
                details={"errors": errors[:10]},
                duration=duration,
            )

    @staticmethod
    def make_test_evaluator(
        command: str,
        cwd: str = ".",
        timeout: int = 120,
    ) -> Callable:
        """Create an evaluator for running tests."""
        def evaluator(context: Dict[str, Any]) -> CriterionResult:
            return Evaluators.run_command(
                command=command,
                cwd=context.get("project_path", cwd),
                timeout=timeout,
                name="test_execution",
            )
        return evaluator

    @staticmethod
    def make_diff_evaluator(max_files: int = 10, project_path: str = ".") -> Callable:
        """Create an evaluator for checking diff size."""
        def evaluator(context: Dict[str, Any]) -> CriterionResult:
            return Evaluators.check_files_changed(
                max_files=max_files,
                project_path=context.get("project_path", project_path),
            )
        return evaluator

    @staticmethod
    def make_type_check_evaluator(command: str = "mypy .", project_path: str = ".") -> Callable:
        """Create an evaluator for type checking."""
        def evaluator(context: Dict[str, Any]) -> CriterionResult:
            return Evaluators.run_command(
                command=command,
                cwd=context.get("project_path", project_path),
                name="type_check",
            )
        return evaluator

    @staticmethod
    def make_lint_evaluator(command: str = "ruff check .", project_path: str = ".") -> Callable:
        """Create an evaluator for linting."""
        def evaluator(context: Dict[str, Any]) -> CriterionResult:
            return Evaluators.run_command(
                command=command,
                cwd=context.get("project_path", project_path),
                name="lint_check",
            )
        return evaluator