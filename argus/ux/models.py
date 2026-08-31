"""UX data models for ARGUS product layer."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LifecyclePhase(Enum):
    """Agent execution lifecycle phases."""
    IDLE = "idle"
    UNDERSTAND = "understand"
    INVESTIGATE = "investigate"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    REPLAN = "replan"
    RECOVER = "recover"
    REPAIR = "repair"
    REVIEW = "review"
    FINALIZE = "finalize"


class StepStatus(Enum):
    """Status of a plan step."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"


class EventSeverity(Enum):
    """Severity levels for UI events."""
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PanelView(Enum):
    """Available panel views."""
    PLAN = "plan"
    PROVIDERS = "providers"
    SECURITY = "security"
    PERFORMANCE = "performance"
    VERIFICATION = "verification"
    RECOVERY = "recovery"
    REVIEW = "review"
    REPLAY = "replay"
    EVENTS = "events"


@dataclass
class PlanStep:
    """A single step in the execution plan."""
    step_id: str = ""
    objective: str = ""
    status: StepStatus = StepStatus.PENDING
    capabilities: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    verification_passed: Optional[bool] = None
    recovery_attempts: int = 0
    details: str = ""


@dataclass
class ExecutionPlan:
    """The current execution plan."""
    run_id: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    current_step_index: int = 0
    total_steps: int = 0

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)


@dataclass
class UIEvent:
    """An event for UI display."""
    event_id: str = ""
    event_type: str = ""
    severity: EventSeverity = EventSeverity.INFO
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: Optional[str] = None
    capability_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderStatus:
    """Provider status for display."""
    provider: str = ""
    model: str = ""
    health: str = "unknown"
    circuit_state: str = "closed"
    latency_seconds: float = 0.0
    retry_count: int = 0
    fallback_count: int = 0
    token_usage: int = 0


@dataclass
class SecurityStatus:
    """Security status for display."""
    allowed_count: int = 0
    approval_count: int = 0
    denied_count: int = 0
    injection_attempts: int = 0
    risk_level: str = "low"
    last_event: Optional[str] = None


@dataclass
class PerformanceStatus:
    """Performance status for display."""
    runtime_seconds: float = 0.0
    active_operations: int = 0
    tool_calls: int = 0
    queue_size: int = 0
    tokens_used: int = 0
    retry_count: int = 0
    recovery_count: int = 0


@dataclass
class VerificationStatus:
    """Verification status for display."""
    criteria: Dict[str, bool] = field(default_factory=dict)
    passed: int = 0
    failed: int = 0
    total: int = 0
    confidence: float = 0.0
    status: str = "incomplete"


@dataclass
class RecoveryStatus:
    """Recovery status for display."""
    attempts: int = 0
    max_attempts: int = 3
    replans: int = 0
    repairs: int = 0
    last_failure: str = ""
    last_action: str = ""
    status: str = "idle"


@dataclass
class ReviewStatus:
    """Review status for display."""
    findings: Dict[str, str] = field(default_factory=dict)
    passed: int = 0
    failed: int = 0
    total: int = 0
    final_verdict: str = "pending"


@dataclass
class UXConfiguration:
    """UX configuration settings."""
    theme: str = "default"
    verbosity: str = "normal"
    event_density: str = "normal"
    animations: bool = True
    approval_behavior: str = "ask"
    default_view: str = "plan"
    performance_display: bool = True
    timestamps: bool = True
    compact_mode: bool = False
    unicode: bool = True
    color: bool = True
    max_event_history: int = 100


@dataclass
class SessionInfo:
    """Session/run information."""
    session_id: str = ""
    run_id: str = ""
    status: str = "idle"
    started_at: str = ""
    task_description: str = ""
    provider: str = ""
    model: str = ""
