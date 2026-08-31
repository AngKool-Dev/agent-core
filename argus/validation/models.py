"""Validation data models for ARGUS real-world agent validation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import uuid


class ValidationTier(Enum):
    """Validation scenario tiers by complexity."""
    TIER_1 = "tier_1"  # Single-tool, deterministic
    TIER_2 = "tier_2"  # Multi-tool, single-domain
    TIER_3 = "tier_3"  # Multi-domain, stateful
    TIER_4 = "tier_4"  # Ambiguous, recovery-required
    TIER_5 = "tier_5"  # Adversarial, security-sensitive


class ValidationCategory(Enum):
    """Categories for validation scenarios."""
    FILE_MANIPULATION = "file_manipulation"
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    GIT_WORKFLOW = "git_workflow"
    DEPENDENCY_MANAGEMENT = "dependency_management"
    SECURITY = "security"
    MULTI_STEP_REASONING = "multi_step_reasoning"


class ValidationStatus(Enum):
    """Status of a validation run."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


class OutcomeType(Enum):
    """Classification of validation outcomes."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    SECURITY_BLOCKED = "security_blocked"
    RECOVERY_SUCCESS = "recovery_success"
    TIMEOUT = "timeout"
    ERROR = "error"


class ContractViolation(Enum):
    """Types of contract violations."""
    OUTPUT_FORMAT = "output_format"
    TOOL_USAGE = "tool_usage"
    SAFETY_BOUNDARY = "safety_boundary"
    STATE_MUTATION = "state_mutation"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    VERIFICATION_FAILURE = "verification_failure"
    RECOVERY_FAILURE = "recovery_failure"


@dataclass
class ValidationConstraint:
    """A constraint that must hold during validation."""
    name: str
    description: str
    check: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationScenario:
    """A real-world validation scenario."""
    scenario_id: str
    name: str
    description: str
    category: ValidationCategory
    tier: ValidationTier
    prompt: str
    expected_outcome: str
    success_criteria: List[str] = field(default_factory=list)
    constraints: List[ValidationConstraint] = field(default_factory=list)
    initial_state: Dict[str, str] = field(default_factory=dict)
    expected_files: List[str] = field(default_factory=list)
    forbidden_files: List[str] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tier": self.tier.value,
            "prompt": self.prompt,
            "expected_outcome": self.expected_outcome,
            "success_criteria": self.success_criteria,
            "initial_state": self.initial_state,
            "expected_files": self.expected_files,
            "forbidden_files": self.forbidden_files,
            "expected_tools": self.expected_tools,
            "forbidden_tools": self.forbidden_tools,
            "timeout_seconds": self.timeout_seconds,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class ToolCallRecord:
    """Record of a tool call during validation."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Any = None
    success: bool = True
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ValidationResult:
    """Result of running a validation scenario."""
    result_id: str = field(default_factory=lambda: f"val-{uuid.uuid4().hex[:8]}")
    scenario_id: str = ""
    status: ValidationStatus = ValidationStatus.PENDING
    outcome: OutcomeType = OutcomeType.FAILURE
    success: bool = False
    duration_seconds: float = 0.0
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    output: str = ""
    errors: List[str] = field(default_factory=list)
    contract_violations: List[ContractViolation] = field(default_factory=list)
    verification_results: Dict[str, bool] = field(default_factory=dict)
    recovery_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)

    @property
    def successful_tool_calls(self) -> int:
        return sum(1 for t in self.tool_calls if t.success)

    @property
    def failed_tool_calls(self) -> int:
        return sum(1 for t in self.tool_calls if not t.success)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "outcome": self.outcome.value,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "tool_calls": [
                {
                    "tool_name": t.tool_name,
                    "arguments": t.arguments,
                    "success": t.success,
                    "duration_ms": t.duration_ms,
                    "timestamp": t.timestamp,
                }
                for t in self.tool_calls
            ],
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
            "output": self.output,
            "errors": self.errors,
            "contract_violations": [v.value for v in self.contract_violations],
            "verification_results": self.verification_results,
            "recovery_attempts": self.recovery_attempts,
            "metadata": self.metadata,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ValidationRun:
    """A complete validation run with multiple scenarios."""
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    scenario_results: Dict[str, ValidationResult] = field(default_factory=dict)
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total_duration: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_scenarios == 0:
            return 0.0
        return self.passed / self.total_scenarios

    @property
    def pass_rate(self) -> float:
        return self.success_rate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_results": {
                k: v.to_dict() for k, v in self.scenario_results.items()
            },
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "total_duration": self.total_duration,
            "success_rate": self.success_rate,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


@dataclass
class ContractClause:
    """A single clause in the Real Agent Outcome Contract."""
    clause_id: str
    name: str
    description: str
    violation_type: ContractViolation
    check: Callable
    required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutcomeContract:
    """Real Agent Outcome Contract - defines what 'done' means."""
    contract_id: str = field(default_factory=lambda: f"contract-{uuid.uuid4().hex[:8]}")
    name: str = "Real Agent Outcome Contract"
    description: str = "Defines the contract for successful agent task completion"
    clauses: List[ContractClause] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, result: ValidationResult) -> List[ContractViolation]:
        """Evaluate a result against this contract."""
        violations = []
        for clause in self.clauses:
            try:
                if not clause.check(result):
                    violations.append(clause.violation_type)
            except Exception:
                if clause.required:
                    violations.append(clause.violation_type)
        return violations


@dataclass
class ValidationConfig:
    """Configuration for a validation run."""
    config_id: str = field(default_factory=lambda: f"val-config-{uuid.uuid4().hex[:8]}")
    scenario_ids: Optional[List[str]] = None
    timeout_seconds: int = 300
    max_recovery_attempts: int = 3
    enable_security_checks: bool = True
    enable_verification: bool = True
    enable_contract_enforcement: bool = True
    parallel: bool = False
    max_workers: int = 1
    output_format: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)
