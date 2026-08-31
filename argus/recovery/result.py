"""Recovery result and state types."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RecoveryStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    EXHAUSTED = "exhausted"
    ESCALATED = "escalated"
    SKIPPED = "skipped"


class FailureClass(str, Enum):
    """Classification of failure types."""
    TRANSIENT = "transient"
    BACKEND = "backend"
    EXECUTION = "execution"
    CODE = "code"
    LOGICAL = "logical"
    ENVIRONMENT = "environment"
    USER_REQUIRED = "user_required"
    UNKNOWN = "unknown"


class RecoveryStrategyType(str, Enum):
    """Types of recovery strategies."""
    RETRY = "retry"
    FALLBACK = "fallback"
    REPLAN = "replan"
    REPAIR = "repair"
    BACKEND_SWITCH = "backend_switch"
    ESCALATE = "escalate"
    SKIP = "skip"


@dataclass
class FailureEvidence:
    """Evidence captured from a failure."""
    failure_class: FailureClass
    message: str
    command: str = ""
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_class": self.failure_class.value,
            "message": self.message,
            "command": self.command,
            "return_code": self.return_code,
            "stdout": self.stdout[:1000],
            "stderr": self.stderr[:1000],
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class RecoveryAction:
    """A single recovery action taken."""
    strategy: RecoveryStrategyType
    description: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    success: bool = False
    duration: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "description": self.description,
            "success": self.success,
            "duration": self.duration,
            "timestamp": self.timestamp,
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    status: RecoveryStatus
    original_failure: Optional[FailureEvidence] = None
    actions: List[RecoveryAction] = field(default_factory=list)
    final_output: Any = None
    message: str = ""
    duration: float = 0.0
    budget_remaining: Dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == RecoveryStatus.SUCCESS

    @property
    def action_count(self) -> int:
        return len(self.actions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "original_failure": self.original_failure.to_dict() if self.original_failure else None,
            "actions": [a.to_dict() for a in self.actions],
            "message": self.message,
            "duration": self.duration,
            "budget_remaining": self.budget_remaining,
        }