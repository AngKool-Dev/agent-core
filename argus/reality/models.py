"""Production reality data models for ARGUS qualification."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class RealityStatus(Enum):
    """Status of a reality validation check."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    ERROR = "error"


class ProviderAvailability(Enum):
    """Provider availability classification."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    NETWORK_FAILED = "network_failed"
    INVALID_RESPONSE = "invalid_response"
    TIMEOUT = "timeout"
    QUARANTINED = "quarantined"
    SKIPPED = "skipped"


class FailureCategory(Enum):
    """Classification of failure types."""
    AGENT_FAILURE = "agent_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    EXTERNAL_PROVIDER_FAILURE = "external_provider_failure"
    CONFIGURATION_FAILURE = "configuration_failure"
    SECURITY_BLOCK = "security_block"
    EXPECTED_DENIAL = "expected_denial"
    SKIPPED = "skipped"


class InvariantId(Enum):
    """Cross-system invariant identifiers."""
    REAL_001 = "real_001"
    REAL_002 = "real_002"
    REAL_003 = "real_003"
    REAL_004 = "real_004"
    REAL_005 = "real_005"
    REAL_006 = "real_006"
    REAL_007 = "real_007"
    REAL_008 = "real_008"
    REAL_009 = "real_009"
    REAL_010 = "real_010"
    REAL_011 = "real_011"
    REAL_012 = "real_012"
    REAL_013 = "real_013"
    REAL_014 = "real_014"
    REAL_015 = "real_015"
    REAL_016 = "real_016"
    REAL_017 = "real_017"
    REAL_018 = "real_018"
    REAL_019 = "real_019"
    REAL_020 = "real_020"
    REAL_021 = "real_021"
    REAL_022 = "real_022"
    REAL_023 = "real_023"
    REAL_024 = "real_024"
    REAL_025 = "real_025"
    REAL_026 = "real_026"
    REAL_027 = "real_027"
    REAL_028 = "real_028"
    REAL_029 = "real_029"
    REAL_030 = "real_030"


@dataclass
class EnvironmentInfo:
    """Captured production environment information."""
    python_version: str = ""
    os_name: str = ""
    os_version: str = ""
    architecture: str = ""
    executable_path: str = ""
    working_directory: str = ""
    argus_version: str = ""
    git_revision: str = ""
    package_installation_mode: str = ""
    environment_variables: Dict[str, str] = field(default_factory=dict)
    provider_configurations: Dict[str, bool] = field(default_factory=dict)
    mcp_configurations: Dict[str, bool] = field(default_factory=dict)
    filesystem_capabilities: Dict[str, bool] = field(default_factory=dict)
    subprocess_availability: Dict[str, bool] = field(default_factory=dict)
    shell_available: bool = False
    terminal_encoding: str = ""
    locale: str = ""
    path_separator: str = ""
    timezone: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "python_version": self.python_version,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "executable_path": self.executable_path,
            "working_directory": self.working_directory,
            "argus_version": self.argus_version,
            "git_revision": self.git_revision,
            "package_installation_mode": self.package_installation_mode,
            "environment_variables": self.environment_variables,
            "provider_configurations": self.provider_configurations,
            "mcp_configurations": self.mcp_configurations,
            "filesystem_capabilities": self.filesystem_capabilities,
            "subprocess_availability": self.subprocess_availability,
            "shell_available": self.shell_available,
            "terminal_encoding": self.terminal_encoding,
            "locale": self.locale,
            "path_separator": self.path_separator,
            "timezone": self.timezone,
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderCheckResult:
    """Result of a provider validation check."""
    provider_name: str
    availability: ProviderAvailability
    lifecycle_stage: str = ""
    duration_ms: float = 0.0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "availability": self.availability.value,
            "lifecycle_stage": self.lifecycle_stage,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class MCPCheckResult:
    """Result of an MCP validation check."""
    server_name: str
    status: RealityStatus
    lifecycle_stage: str = ""
    duration_ms: float = 0.0
    security_passed: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_name": self.server_name,
            "status": self.status.value,
            "lifecycle_stage": self.lifecycle_stage,
            "duration_ms": self.duration_ms,
            "security_passed": self.security_passed,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class SubprocessCheckResult:
    """Result of a subprocess validation check."""
    command: str
    status: RealityStatus
    exit_code: int = -1
    stdout_captured: bool = False
    stderr_captured: bool = False
    duration_ms: float = 0.0
    timed_out: bool = False
    cancelled: bool = False
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout_captured": self.stdout_captured,
            "stderr_captured": self.stderr_captured,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class CrashResumeResult:
    """Result of a crash/resume validation check."""
    crash_point: str
    status: RealityStatus
    detected_crash: bool = False
    journal_intact: bool = False
    state_reconstructed: bool = False
    unknown_preserved: bool = False
    recovery_budget_preserved: bool = False
    security_policy_preserved: bool = False
    resume_successful: bool = False
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crash_point": self.crash_point,
            "status": self.status.value,
            "detected_crash": self.detected_crash,
            "journal_intact": self.journal_intact,
            "state_reconstructed": self.state_reconstructed,
            "unknown_preserved": self.unknown_preserved,
            "recovery_budget_preserved": self.recovery_budget_preserved,
            "security_policy_preserved": self.security_policy_preserved,
            "resume_successful": self.resume_successful,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class WindowsCheckResult:
    """Result of a Windows-specific validation check."""
    check_name: str
    status: RealityStatus
    path_tested: str = ""
    security_scope_maintained: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "path_tested": self.path_tested,
            "security_scope_maintained": self.security_scope_maintained,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class SecretCanaryResult:
    """Result of a secret canary audit."""
    artifact_name: str
    canary_detected: bool = False
    redaction_effective: bool = True
    locations_found: List[str] = field(default_factory=list)
    status: RealityStatus = RealityStatus.PASSED
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_name": self.artifact_name,
            "canary_detected": self.canary_detected,
            "redaction_effective": self.redaction_effective,
            "locations_found": self.locations_found,
            "status": self.status.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class InvariantResult:
    """Result of an invariant check."""
    invariant_id: InvariantId
    description: str
    passed: bool = False
    evidence: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant_id": self.invariant_id.value,
            "description": self.description,
            "passed": self.passed,
            "evidence": self.evidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class RealityScenarioResult:
    """Result of an end-to-end reality scenario."""
    scenario_id: str
    status: RealityStatus
    failure_category: FailureCategory = FailureCategory.AGENT_FAILURE
    environment: Optional[EnvironmentInfo] = None
    provider_used: str = ""
    capabilities_used: List[str] = field(default_factory=list)
    events_emitted: int = 0
    security_decisions: int = 0
    tool_calls: int = 0
    state_transitions: int = 0
    verification_passed: bool = False
    recovery_attempts: int = 0
    review_passed: bool = False
    duration_seconds: float = 0.0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "failure_category": self.failure_category.value,
            "provider_used": self.provider_used,
            "capabilities_used": self.capabilities_used,
            "events_emitted": self.events_emitted,
            "security_decisions": self.security_decisions,
            "tool_calls": self.tool_calls,
            "state_transitions": self.state_transitions,
            "verification_passed": self.verification_passed,
            "recovery_attempts": self.recovery_attempts,
            "review_passed": self.review_passed,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class RealityRun:
    """A complete reality validation run."""
    run_id: str = field(default_factory=lambda: f"reality-{uuid.uuid4().hex[:8]}")
    environment: Optional[EnvironmentInfo] = None
    provider_results: Dict[str, ProviderCheckResult] = field(default_factory=dict)
    mcp_results: Dict[str, MCPCheckResult] = field(default_factory=dict)
    subprocess_results: Dict[str, SubprocessCheckResult] = field(default_factory=dict)
    crash_resume_results: Dict[str, CrashResumeResult] = field(default_factory=dict)
    windows_results: Dict[str, WindowsCheckResult] = field(default_factory=dict)
    secret_canary_results: Dict[str, SecretCanaryResult] = field(default_factory=dict)
    invariant_results: Dict[str, InvariantResult] = field(default_factory=dict)
    scenario_results: Dict[str, RealityScenarioResult] = field(default_factory=dict)
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    inconclusive: int = 0
    infrastructure_failures: int = 0
    total_duration: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return self.passed / self.total_checks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "environment": self.environment.to_dict() if self.environment else None,
            "provider_results": {k: v.to_dict() for k, v in self.provider_results.items()},
            "mcp_results": {k: v.to_dict() for k, v in self.mcp_results.items()},
            "subprocess_results": {k: v.to_dict() for k, v in self.subprocess_results.items()},
            "crash_resume_results": {k: v.to_dict() for k, v in self.crash_resume_results.items()},
            "windows_results": {k: v.to_dict() for k, v in self.windows_results.items()},
            "secret_canary_results": {k: v.to_dict() for k, v in self.secret_canary_results.items()},
            "invariant_results": {k: v.to_dict() for k, v in self.invariant_results.items()},
            "scenario_results": {k: v.to_dict() for k, v in self.scenario_results.items()},
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "inconclusive": self.inconclusive,
            "infrastructure_failures": self.infrastructure_failures,
            "total_duration": self.total_duration,
            "pass_rate": self.pass_rate,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


@dataclass
class ReleaseDecision:
    """Release qualification decision."""
    decision: str = "BLOCKED"
    version: str = "1.0.0"
    evidence: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "version": self.version,
            "evidence": self.evidence,
            "limitations": self.limitations,
            "risks": self.risks,
            "timestamp": self.timestamp,
        }
