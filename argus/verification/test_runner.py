"""Test runner for verification."""

import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.verification.result import CriterionResult, VerificationStatus


@dataclass
class TestRunResult:
    """Result of a test run."""
    command: str
    success: bool
    return_code: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    test_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    error_count: int = 0
    skipped_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "success": self.success,
            "return_code": self.return_code,
            "stdout": self.stdout[:2000],
            "stderr": self.stderr[:2000],
            "duration": self.duration,
            "test_count": self.test_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
        }


class TestRunner:
    """Runs tests and parses results."""

    def __init__(self, default_timeout: int = 120):
        self._default_timeout = default_timeout

    def run(
        self,
        command: str,
        cwd: str = ".",
        timeout: Optional[int] = None,
    ) -> TestRunResult:
        """Run a test command."""
        timeout = timeout or self._default_timeout
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

            test_result = TestRunResult(
                command=command,
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
            )

            # Parse test output
            self._parse_output(test_result)

            return test_result

        except subprocess.TimeoutExpired:
            return TestRunResult(
                command=command,
                success=False,
                return_code=-1,
                stderr=f"Test timed out after {timeout}s",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestRunResult(
                command=command,
                success=False,
                return_code=-1,
                stderr=str(e),
                duration=time.time() - start,
            )

    def _parse_output(self, result: TestRunResult) -> None:
        """Parse test output to extract counts."""
        output = result.stdout + result.stderr

        # Try pytest output format
        import re

        # "X passed, Y failed, Z errors" or "X passed"
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        error_match = re.search(r"(\d+)\s+error", output)
        skipped_match = re.search(r"(\d+)\s+skipped", output)

        if passed_match:
            result.pass_count = int(passed_match.group(1))
        if failed_match:
            result.fail_count = int(failed_match.group(1))
        if error_match:
            result.error_count = int(error_match.group(1))
        if skipped_match:
            result.skipped_count = int(skipped_match.group(1))

        result.test_count = result.pass_count + result.fail_count + result.error_count + result.skipped_count

    def run_pytest(
        self,
        path: str = ".",
        cwd: str = ".",
        timeout: Optional[int] = None,
    ) -> TestRunResult:
        """Run pytest."""
        return self.run(f"pytest {path} -v", cwd=cwd, timeout=timeout)

    def run_cargo_test(
        self,
        cwd: str = ".",
        timeout: Optional[int] = None,
    ) -> TestRunResult:
        """Run cargo test."""
        return self.run("cargo test", cwd=cwd, timeout=timeout)

    def run_npm_test(
        self,
        cwd: str = ".",
        timeout: Optional[int] = None,
    ) -> TestRunResult:
        """Run npm test."""
        return self.run("npm test", cwd=cwd, timeout=timeout)

    def run_go_test(
        self,
        cwd: str = ".",
        timeout: Optional[int] = None,
    ) -> TestRunResult:
        """Run go test."""
        return self.run("go test ./...", cwd=cwd, timeout=timeout)

    def to_criterion_result(self, test_result: TestRunResult, name: str = "test_execution") -> CriterionResult:
        """Convert a test run result to a criterion result."""
        if test_result.success:
            return CriterionResult(
                name=name,
                status=VerificationStatus.PASSED,
                message=f"Tests passed: {test_result.pass_count} passed, {test_result.fail_count} failed",
                details=test_result.to_dict(),
                duration=test_result.duration,
            )
        else:
            return CriterionResult(
                name=name,
                status=VerificationStatus.FAILED,
                message=f"Tests failed: {test_result.fail_count} failed, {test_result.error_count} errors",
                details=test_result.to_dict(),
                duration=test_result.duration,
            )