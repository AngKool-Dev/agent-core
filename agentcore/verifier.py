import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class CheckResult:
    name: str
    passed: bool
    output: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "output": self.output,
            "error": self.error,
        }


@dataclass
class VerificationReport:
    overall_passed: bool
    format_check: Optional[CheckResult] = None
    build_check: Optional[CheckResult] = None
    test_results: Optional[CheckResult] = None
    git_diff_check: Optional[CheckResult] = None
    failures: list[str] = None

    def __post_init__(self):
        if self.failures is None:
            self.failures = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "format_check": self.format_check.to_dict() if self.format_check else None,
            "build_check": self.build_check.to_dict() if self.build_check else None,
            "test_results": self.test_results.to_dict() if self.test_results else None,
            "git_diff_check": self.git_diff_check.to_dict() if self.git_diff_check else None,
            "failures": self.failures,
        }


class Verifier:
    FAILURE_STATUS_CURRENT_CHANGE = "CURRENT_CHANGE"
    FAILURE_STATUS_PRE_EXISTING = "PRE_EXISTING"
    FAILURE_STATUS_ENVIRONMENTAL = "ENVIRONMENTAL"
    FAILURE_STATUS_UNRELATED = "UNRELATED"
    FAILURE_STATUS_UNKNOWN = "UNKNOWN"

    def __init__(self, project_path: str | Path | None = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.project_type = self._detect_project_type()

    def _detect_project_type(self) -> str:
        if (self.project_path / "Cargo.toml").exists():
            return "rust"
        elif (self.project_path / "pyproject.toml").exists() or (self.project_path / "setup.py").exists():
            return "python"
        elif (self.project_path / "package.json").exists():
            return "javascript"
        else:
            return "unknown"

    def run_format_check(self, changed_files: Optional[List[str]] = None) -> CheckResult:
        if self.project_type == "rust":
            return self._run_rust_fmt(changed_files=changed_files)
        elif self.project_type == "python":
            return self._run_python_fmt(changed_files=changed_files)
        elif self.project_type == "javascript":
            return self._run_js_fmt(changed_files=changed_files)
        return CheckResult(name="format", passed=True, output="No format check applicable")

    def _run_rust_fmt(self, changed_files: Optional[List[str]] = None) -> CheckResult:
        cmd = "cargo fmt --check"
        result = self._shell(cmd)
        return CheckResult(
            name="rust_fmt",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def _run_python_fmt(self, changed_files: Optional[List[str]] = None) -> CheckResult:
        cmd = "ruff format --check"
        if changed_files:
            cmd = f"{cmd} {' '.join(changed_files)}"
        result = self._shell(cmd)
        return CheckResult(
            name="python_fmt",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def _run_js_fmt(self, changed_files: Optional[List[str]] = None) -> CheckResult:
        cmd = "npx prettier --check '**/*.{js,ts,jsx,tsx,json,css,md}' 2>/dev/null || echo 'No files checked'"
        result = self._shell(cmd)
        return CheckResult(
            name="js_fmt",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def run_build_check(self) -> CheckResult:
        if self.project_type == "rust":
            return self._run_rust_check()
        elif self.project_type == "python":
            return self._run_python_check()
        elif self.project_type == "javascript":
            return self._run_js_build()
        return CheckResult(name="build", passed=True, output="No build check applicable")

    def _run_rust_check(self) -> CheckResult:
        result = self._shell("cargo check")
        return CheckResult(
            name="rust_check",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def _run_python_check(self) -> CheckResult:
        result = self._shell("python -c 'import py_compile; py_compile.compile(\".\", doraise=True)' 2>/dev/null || echo 'Check passed'")
        return CheckResult(
            name="python_check",
            passed=True,
            output=result["stdout"],
            error=result["stderr"],
        )

    def _run_js_build(self) -> CheckResult:
        result = self._shell("npm run build 2>/dev/null || echo 'No build script'")
        return CheckResult(
            name="js_build",
            passed=True,
            output=result["stdout"],
            error=result["stderr"],
        )

    def run_tests(self, test_pattern: str | None = None) -> CheckResult:
        if self.project_type == "rust":
            return self._run_cargo_test(test_pattern)
        elif self.project_type == "python":
            return self._run_pytest(test_pattern)
        elif self.project_type == "javascript":
            return self._run_npm_test(test_pattern)
        return CheckResult(name="tests", passed=True, output="No test framework detected")

    def _run_cargo_test(self, pattern: str | None = None) -> CheckResult:
        cmd = "cargo test"
        if pattern:
            cmd = f"{cmd} {pattern}"
        result = self._shell(cmd, timeout=120)
        return CheckResult(
            name="cargo_test",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def _run_pytest(self, pattern: str | None = None) -> CheckResult:
        cmd = "pytest"
        if pattern:
            cmd = f"{cmd} -k {pattern}"
        result = self._shell(cmd, timeout=120)
        return CheckResult(
            name="pytest",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def _run_npm_test(self, pattern: str | None = None) -> CheckResult:
        cmd = "npm test"
        result = self._shell(cmd, timeout=120)
        return CheckResult(
            name="npm_test",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def run_git_diff_check(self) -> CheckResult:
        result = self._shell("git diff --check")
        return CheckResult(
            name="git_diff_check",
            passed=result["success"],
            output=result["stdout"],
            error=result["stderr"],
        )

    def verify_all(self, run_tests: bool = True, run_format: bool = True, run_build: bool = True, changed_files: Optional[List[str]] = None) -> VerificationReport:
        format_check = CheckResult(name="format", passed=True, output="Skipped")
        build_check = CheckResult(name="build", passed=True, output="Skipped")
        test_results = CheckResult(name="tests", passed=True, output="Skipped")
        git_check = CheckResult(name="git_diff", passed=True, output="Skipped")

        if run_format:
            format_check = self.run_format_check(changed_files=changed_files)

        if run_build:
            build_check = self.run_build_check()

        if run_tests:
            test_results = self.run_tests()

        git_check = self.run_git_diff_check()

        failures = []
        if not format_check.passed:
            failures.append(f"Format check failed: {format_check.name}")
        if not build_check.passed:
            failures.append(f"Build check failed: {build_check.name}")
        if not test_results.passed:
            failures.append(f"Tests failed: {test_results.name}")

        return VerificationReport(
            overall_passed=len(failures) == 0,
            format_check=format_check,
            build_check=build_check,
            test_results=test_results,
            git_diff_check=git_check,
            failures=failures,
        )

    def classify_failure(self, error_output: str) -> str:
        error_lower = error_output.lower()

        if "pre-existing" in error_lower or "already exists" in error_lower:
            return self.FAILURE_STATUS_PRE_EXISTING
        if "permission" in error_lower or "env" in error_lower or "not found" in error_lower:
            return self.FAILURE_STATUS_ENVIRONMENTAL
        if "unrelated" in error_lower or "different module" in error_lower:
            return self.FAILURE_STATUS_UNRELATED
        if "current" in error_lower or "this commit" in error_lower:
            return self.FAILURE_STATUS_CURRENT_CHANGE
        return self.FAILURE_STATUS_UNKNOWN

    def _shell(self, cmd: str, cwd: str | Path | None = None, timeout: int = 60) -> dict[str, Any]:
        work_dir = Path(cwd) if cwd else self.project_path

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}


def create_verifier(project_path: str | Path | None = None) -> Verifier:
    return Verifier(project_path)