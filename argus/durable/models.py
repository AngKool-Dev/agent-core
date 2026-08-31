"""ARGUS Durable Execution data models."""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class OperationStatus(str, Enum):
    """Status of an operation in the execution journal."""
    INTENT = "intent"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILED = "reconcilied"
    RECONCILED_COMPLETED = "reconciled_completed"
    RECONCILED_NOT_EXECUTED = "reconciled_not_executed"
    REQUIRES_DECISION = "requires_decision"


class OperationType(str, Enum):
    """Types of operations that can be journaled."""
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    SHELL_EXECUTE = "shell.execute"
    GIT_OPERATION = "git.operation"
    MCP_TOOL = "mcp.tool"
    MODEL_CALL = "model.call"
    VERIFICATION = "verification"
    RECOVERY = "recovery"
    REVIEW = "review"
    CAPABILITY = "capability"
    STATE_COMMIT = "state.commit"
    CHECKPOINT = "checkpoint"


class RunStatus(str, Enum):
    """Status of an execution run."""
    RUNNING = "running"
    PAUSED = "paused"
    CRASHED = "crashed"
    RECOVERABLE = "recoverable"
    RECONCILING = "reconciling"
    RESUMING = "resuming"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class CrashPoint(str, Enum):
    """Points where a crash can be injected."""
    BEFORE_INTENT = "before_intent"
    AFTER_INTENT = "after_intent"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    DURING_OPERATION = "during_operation"
    AFTER_OPERATION = "after_operation"
    BEFORE_COMPLETION = "before_completion"
    AFTER_COMPLETION = "after_completion"
    BEFORE_STATE_COMMIT = "before_state_commit"
    AFTER_STATE_COMMIT = "after_state_commit"
    BEFORE_CHECKPOINT = "before_checkpoint"
    AFTER_CHECKPOINT = "after_checkpoint"
    BEFORE_VERIFICATION = "before_verification"
    DURING_VERIFICATION = "during_verification"
    AFTER_VERIFICATION = "after_verification"
    BEFORE_RECOVERY = "before_recovery"
    DURING_RECOVERY = "during_recovery"
    AFTER_RECOVERY = "after_recovery"
    BEFORE_REVIEW = "before_review"
    DURING_REVIEW = "during_review"
    AFTER_REVIEW = "after_review"


class CheckpointPhase(str, Enum):
    """Phases where checkpoints can be taken."""
    BEFORE_PLAN = "before_plan"
    AFTER_PLAN = "after_plan"
    BEFORE_CAPABILITY = "before_capability"
    AFTER_CAPABILITY = "after_capability"
    BEFORE_EXECUTION = "before_execution"
    AFTER_EXECUTION = "after_execution"
    BEFORE_VERIFICATION = "before_verification"
    AFTER_VERIFICATION = "after_verification"
    BEFORE_RECOVERY = "before_recovery"
    AFTER_RECOVERY = "after_recovery"
    BEFORE_REVIEW = "before_review"
    AFTER_REVIEW = "after_review"


class IdempotencyClass(str, Enum):
    """Classification of operation idempotency."""
    IDEMPOTENT = "idempotent"
    CONDITIONALLY_IDEMPOTENT = "conditionally_idempotent"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"


class RetryPolicy(str, Enum):
    """Policy for retrying operations."""
    SAFE_RETRY = "safe_retry"
    UNSAFE_RETRY = "unsafe_retry"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    APPROVAL_REQUIRED = "approval_required"
    USER_DECISION = "user_decision"


class ReconciliationDecision(str, Enum):
    """Decision for reconciling UNKNOWN operations."""
    RETRY = "retry"
    SKIP = "skip"
    MARK_COMPLETED = "mark_completed"
    MARK_FAILED = "mark_failed"
    REQUIRE_USER = "require_user"


class ResumeMode(str, Enum):
    """Mode for resuming execution."""
    NORMAL = "normal"
    DRY_RUN = "dry_run"
    RECONCILE = "reconcile"


class LockState(str, Enum):
    """State of a run lock."""
    ACQUIRED = "acquired"
    RELEASED = "released"
    STALE = "stale"
    EXPIRED = "expired"


@dataclass
class OperationIdentity:
    """Stable identity for a potentially side-effecting operation."""
    operation_id: str
    run_id: str
    session_id: str
    capability_id: str
    operation_type: OperationType
    target: str
    normalized_arguments: Dict[str, Any] = field(default_factory=dict)
    attempt: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "capability_id": self.capability_id,
            "operation_type": self.operation_type.value,
            "target": self.target,
            "normalized_arguments": self.normalized_arguments,
            "attempt": self.attempt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationIdentity":
        return cls(
            operation_id=data["operation_id"],
            run_id=data["run_id"],
            session_id=data["session_id"],
            capability_id=data["capability_id"],
            operation_type=OperationType(data["operation_type"]),
            target=data["target"],
            normalized_arguments=data.get("normalized_arguments", {}),
            attempt=data.get("attempt", 1),
        )

    def fingerprint(self) -> str:
        """Generate a deterministic fingerprint for duplicate detection."""
        content = f"{self.run_id}:{self.capability_id}:{self.operation_type.value}:{self.target}"
        args_sorted = str(sorted(self.normalized_arguments.items()))
        content += f":{args_sorted}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class OperationRecord:
    """A single operation record in the execution journal."""
    identity: OperationIdentity
    status: OperationStatus
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    reconciliation: Optional[str] = None
    parent_operation_id: Optional[str] = None
    child_operation_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evidence": self.evidence,
            "error": self.error,
            "reconciliation": self.reconciliation,
            "parent_operation_id": self.parent_operation_id,
            "child_operation_ids": self.child_operation_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationRecord":
        return cls(
            identity=OperationIdentity.from_dict(data["identity"]),
            status=OperationStatus(data["status"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            evidence=data.get("evidence", {}),
            error=data.get("error"),
            reconciliation=data.get("reconciliation"),
            parent_operation_id=data.get("parent_operation_id"),
            child_operation_ids=data.get("child_operation_ids", []),
        )


@dataclass
class OperationJournal:
    """Journal of operations for a run."""
    run_id: str
    operations: List[OperationRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_operation(self, record: OperationRecord):
        """Add an operation record to the journal."""
        self.operations.append(record)
        self.updated_at = datetime.utcnow().isoformat()

    def get_operation(self, operation_id: str) -> Optional[OperationRecord]:
        """Get an operation by ID."""
        for op in self.operations:
            if op.identity.operation_id == operation_id:
                return op
        return None

    def get_operations_by_status(self, status: OperationStatus) -> List[OperationRecord]:
        """Get all operations with a given status."""
        return [op for op in self.operations if op.status == status]

    def get_unknown_operations(self) -> List[OperationRecord]:
        """Get all UNKNOWN operations."""
        return self.get_operations_by_status(OperationStatus.UNKNOWN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "operations": [op.to_dict() for op in self.operations],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationJournal":
        return cls(
            run_id=data["run_id"],
            operations=[OperationRecord.from_dict(op) for op in data.get("operations", [])],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass
class Checkpoint:
    """A checkpoint capturing execution state at a specific point."""
    checkpoint_id: str
    run_id: str
    phase: CheckpointPhase
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    state_snapshot: Dict[str, Any] = field(default_factory=dict)
    operation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    integrity_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "run_id": self.run_id,
            "phase": self.phase.value,
            "timestamp": self.timestamp,
            "state_snapshot": self.state_snapshot,
            "operation_id": self.operation_id,
            "metadata": self.metadata,
            "integrity_hash": self.integrity_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            run_id=data["run_id"],
            phase=CheckpointPhase(data["phase"]),
            timestamp=data["timestamp"],
            state_snapshot=data.get("state_snapshot", {}),
            operation_id=data.get("operation_id"),
            metadata=data.get("metadata", {}),
            integrity_hash=data.get("integrity_hash", ""),
        )


@dataclass
class CheckpointPhaseData:
    """Phase-specific checkpoint data."""
    phase: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckpointCapability:
    """Checkpoint data for capability phase."""
    capability_id: str = ""
    capability_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""


@dataclass
class CheckpointExecution:
    """Checkpoint data for execution phase."""
    command: str = ""
    working_directory: str = ""
    started_at: str = ""
    completed_at: str = ""
    exit_code: Optional[int] = None
    output: str = ""


@dataclass
class CheckpointVerification:
    """Checkpoint data for verification phase."""
    criteria: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    passed: bool = False


@dataclass
class CheckpointRecovery:
    """Checkpoint data for recovery phase."""
    failure_type: str = ""
    strategy: str = ""
    attempt: int = 0
    started_at: str = ""
    completed_at: str = ""
    success: bool = False


@dataclass
class CheckpointReview:
    """Checkpoint data for review phase."""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    passed: bool = False


@dataclass
class ExecutionRun:
    """Represents a single execution run."""
    run_id: str
    session_id: str
    task: str
    status: RunStatus = RunStatus.RUNNING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    current_phase: str = ""
    current_step: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    crash_count: int = 0
    resume_count: int = 0
    recovery_budget_used: int = 0
    provider_id: Optional[str] = None
    approval_scopes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "task": self.task,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "metadata": self.metadata,
            "crash_count": self.crash_count,
            "resume_count": self.resume_count,
            "recovery_budget_used": self.recovery_budget_used,
            "provider_id": self.provider_id,
            "approval_scopes": self.approval_scopes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionRun":
        return cls(
            run_id=data["run_id"],
            session_id=data["session_id"],
            task=data["task"],
            status=RunStatus(data["status"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            completed_at=data.get("completed_at"),
            current_phase=data.get("current_phase", ""),
            current_step=data.get("current_step", ""),
            metadata=data.get("metadata", {}),
            crash_count=data.get("crash_count", 0),
            resume_count=data.get("resume_count", 0),
            recovery_budget_used=data.get("recovery_budget_used", 0),
            provider_id=data.get("provider_id"),
            approval_scopes=data.get("approval_scopes", {}),
        )


@dataclass
class LockState:
    """State of a run lock."""
    run_id: str
    owner_id: str
    acquired_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None
    state: str = "acquired"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "owner_id": self.owner_id,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "state": self.state,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LockState":
        return cls(
            run_id=data["run_id"],
            owner_id=data["owner_id"],
            acquired_at=data["acquired_at"],
            expires_at=data.get("expires_at"),
            state=data.get("state", "acquired"),
            metadata=data.get("metadata", {}),
        )


def generate_operation_id() -> str:
    """Generate a unique operation ID."""
    return f"op-{uuid.uuid4().hex[:12]}"


def generate_run_id() -> str:
    """Generate a unique run ID."""
    return f"run-{uuid.uuid4().hex[:12]}"


def generate_checkpoint_id() -> str:
    """Generate a unique checkpoint ID."""
    return f"chk-{uuid.uuid4().hex[:12]}"
