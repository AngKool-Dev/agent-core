"""ARGUS Real-World Task Harness - task definitions and models."""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class TaskCategory(str, Enum):
    """Categories of real-world coding tasks."""
    FIX_FAILING_TEST = "fix_failing_test"
    FIX_COMPILATION_ERROR = "fix_compilation_error"
    ADD_FEATURE = "add_feature"
    REFACTOR_MODULE = "refactor_module"
    UPGRADE_DEPENDENCY = "upgrade_dependency"
    FIX_REGRESSION = "fix_regression"
    DIAGNOSE_BUG = "diagnose_bug"
    MODIFY_MULTIPLE_FILES = "modify_multiple_files"
    FIX_BROKEN_REPO = "broken_repo"


class TaskDifficulty(str, Enum):
    """Difficulty levels for tasks."""
    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class TaskLanguage(str, Enum):
    """Programming languages for tasks."""
    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    MULTI = "multi"


@dataclass
class TaskState:
    """Initial state for a task."""
    files: Dict[str, str]  # path -> content
    git_ref: Optional[str] = None
    installed_packages: Optional[Dict[str, str]] = None  # name -> version
    environment: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": dict(self.files),
            "git_ref": self.git_ref,
            "installed_packages": dict(self.installed_packages) if self.installed_packages else None,
            "environment": dict(self.environment) if self.environment else None,
        }


@dataclass
class SuccessCriteria:
    """Criteria for determining task success."""
    expected_files_modified: Optional[List[str]] = None
    expected_files_created: Optional[List[str]] = None
    expected_files_deleted: Optional[List[str]] = None
    expected_content_contains: Optional[Dict[str, List[str]]] = None  # path -> [strings]
    expected_content_not_contains: Optional[Dict[str, List[str]]] = None
    expected_tests_pass: Optional[List[str]] = None
    expected_tests_fail: Optional[List[str]] = None
    expected_exit_code: Optional[int] = None
    expected_output_contains: Optional[List[str]] = None
    custom_checks: Optional[List[str]] = None  # Names of custom check functions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_files_modified": self.expected_files_modified,
            "expected_files_created": self.expected_files_created,
            "expected_files_deleted": self.expected_files_deleted,
            "expected_content_contains": self.expected_content_contains,
            "expected_content_not_contains": self.expected_content_not_contains,
            "expected_tests_pass": self.expected_tests_pass,
            "expected_tests_fail": self.expected_tests_fail,
            "expected_exit_code": self.expected_exit_code,
            "expected_output_contains": self.expected_output_contains,
            "custom_checks": self.custom_checks,
        }


@dataclass
class TaskConstraints:
    """Constraints on how a task can be solved."""
    allowed_paths: Optional[List[str]] = None
    blocked_paths: Optional[List[str]] = None
    allowed_tools: Optional[List[str]] = None
    blocked_tools: Optional[List[str]] = None
    max_iterations: Optional[int] = None
    max_tool_calls: Optional[int] = None
    max_time_seconds: Optional[int] = None
    require_no_new_dependencies: bool = False
    require_tests_pass: bool = True
    require_no_regression: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_paths": self.allowed_paths,
            "blocked_paths": self.blocked_paths,
            "allowed_tools": self.allowed_tools,
            "blocked_tools": self.blocked_tools,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "max_time_seconds": self.max_time_seconds,
            "require_no_new_dependencies": self.require_no_new_dependencies,
            "require_tests_pass": self.require_tests_pass,
            "require_no_regression": self.require_no_regression,
        }


@dataclass
class BenchmarkTask:
    """A single benchmark task for ARGUS."""
    task_id: str
    name: str
    description: str
    category: TaskCategory
    difficulty: TaskDifficulty
    language: TaskLanguage
    initial_state: TaskState
    success_criteria: SuccessCriteria
    constraints: TaskConstraints = field(default_factory=TaskConstraints)
    expected_changes: Optional[List[str]] = None  # Human-readable description
    expected_tests: Optional[List[str]] = None
    hints: Optional[List[str]] = None
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    timeout_seconds: int = 300

    @property
    def fingerprint(self) -> str:
        """Generate a unique fingerprint for this task."""
        content = f"{self.task_id}:{self.name}:{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "language": self.language.value,
            "initial_state": self.initial_state.to_dict(),
            "success_criteria": self.success_criteria.to_dict(),
            "constraints": self.constraints.to_dict(),
            "expected_changes": self.expected_changes,
            "expected_tests": self.expected_tests,
            "hints": self.hints,
            "tags": self.tags,
            "created_at": self.created_at,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkTask":
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            description=data["description"],
            category=TaskCategory(data["category"]),
            difficulty=TaskDifficulty(data["difficulty"]),
            language=TaskLanguage(data["language"]),
            initial_state=TaskState(**data["initial_state"]),
            success_criteria=SuccessCriteria(**data["success_criteria"]),
            constraints=TaskConstraints(**data.get("constraints", {})),
            expected_changes=data.get("expected_changes"),
            expected_tests=data.get("expected_tests"),
            hints=data.get("hints"),
            tags=data.get("tags", []),
            created_at=data.get("created_at", time.time()),
            timeout_seconds=data.get("timeout_seconds", 300),
        )


@dataclass
class TaskResult:
    """Result of running a benchmark task."""
    task_id: str
    run_id: str
    success: bool
    status: str  # "completed", "failed", "timeout", "error"
    duration_seconds: float
    iterations: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    tokens_used: int = 0
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    tests_passed: List[str] = field(default_factory=list)
    tests_failed: List[str] = field(default_factory=list)
    verification_passed: bool = False
    review_passed: bool = False
    recovery_attempts: int = 0
    security_blocks: int = 0
    error: Optional[str] = None
    output: str = ""
    score: float = 0.0  # 0.0 to 1.0
    findings: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "success": self.success,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "model_calls": self.model_calls,
            "tokens_used": self.tokens_used,
            "files_modified": self.files_modified,
            "files_created": self.files_created,
            "files_deleted": self.files_deleted,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "verification_passed": self.verification_passed,
            "review_passed": self.review_passed,
            "recovery_attempts": self.recovery_attempts,
            "security_blocks": self.security_blocks,
            "error": self.error,
            "output": self.output,
            "score": self.score,
            "findings": self.findings,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class BenchmarkScorecard:
    """Aggregated scorecard for a benchmark run."""
    run_id: str
    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    timed_out: int = 0
    errors: int = 0
    total_duration: float = 0.0
    total_iterations: int = 0
    total_tool_calls: int = 0
    total_model_calls: int = 0
    total_tokens: int = 0
    total_recovery_attempts: int = 0
    total_security_blocks: int = 0
    task_results: List[TaskResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def success_rate(self) -> float:
        return self.completed / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def average_score(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(r.score for r in self.task_results) / len(self.task_results)

    @property
    def average_duration(self) -> float:
        return self.total_duration / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def average_iterations(self) -> float:
        return self.total_iterations / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def average_tool_calls(self) -> float:
        return self.total_tool_calls / self.total_tasks if self.total_tasks > 0 else 0.0

    @property
    def verification_pass_rate(self) -> float:
        verified = [r for r in self.task_results if r.verification_passed]
        return len(verified) / len(self.task_results) if self.task_results else 0.0

    @property
    def review_pass_rate(self) -> float:
        reviewed = [r for r in self.task_results if r.review_passed]
        return len(reviewed) / len(self.task_results) if self.task_results else 0.0

    @property
    def recovery_rate(self) -> float:
        recovered = [r for r in self.task_results if r.recovery_attempts > 0 and r.success]
        attempted = [r for r in self.task_results if r.recovery_attempts > 0]
        return len(recovered) / len(attempted) if attempted else 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_tasks": self.total_tasks,
            "completed": self.completed,
            "failed": self.failed,
            "timed_out": self.timed_out,
            "errors": self.errors,
            "total_duration": self.total_duration,
            "total_iterations": self.total_iterations,
            "total_tool_calls": self.total_tool_calls,
            "total_model_calls": self.total_model_calls,
            "total_tokens": self.total_tokens,
            "total_recovery_attempts": self.total_recovery_attempts,
            "total_security_blocks": self.total_security_blocks,
            "success_rate": self.success_rate,
            "average_score": self.average_score,
            "average_duration": self.average_duration,
            "average_iterations": self.average_iterations,
            "average_tool_calls": self.average_tool_calls,
            "verification_pass_rate": self.verification_pass_rate,
            "review_pass_rate": self.review_pass_rate,
            "recovery_rate": self.recovery_rate,
            "task_results": [r.to_dict() for r in self.task_results],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def summary(self) -> str:
        lines = [
            "ARGUS SCORECARD",
            "=" * 50,
            f"Run ID: {self.run_id}",
            f"Total Tasks: {self.total_tasks}",
            f"Completed: {self.completed}",
            f"Failed: {self.failed}",
            f"Timed Out: {self.timed_out}",
            f"Errors: {self.errors}",
            "",
            f"Success Rate: {self.success_rate:.1%}",
            f"Average Score: {self.average_score:.2f}",
            f"Average Duration: {self.average_duration:.1f}s",
            f"Average Iterations: {self.average_iterations:.1f}",
            f"Average Tool Calls: {self.average_tool_calls:.1f}",
            "",
            f"Verification Pass Rate: {self.verification_pass_rate:.1%}",
            f"Review Pass Rate: {self.review_pass_rate:.1%}",
            f"Recovery Rate: {self.recovery_rate:.1%}",
            "",
            f"Total Tokens: {self.total_tokens}",
            f"Total Recovery Attempts: {self.total_recovery_attempts}",
            f"Total Security Blocks: {self.total_security_blocks}",
        ]
        return "\n".join(lines)
