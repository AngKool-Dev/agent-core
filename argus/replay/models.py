"""ARGUS Replay data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class RunStatus(str, Enum):
    """Status of a replay run."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    CORRUPTED = "corrupted"
    INCONSISTENT = "inconsistent"


class EventIntegrity(str, Enum):
    """Integrity classification for events."""
    VALID = "valid"
    WARNING = "warning"
    INCONSISTENT = "inconsistent"
    CORRUPTED = "corrupted"


@dataclass
class ReplayEvent:
    """Normalized replay representation of an event."""
    sequence: int
    event_id: str
    timestamp: float
    event_type: str
    category: str
    source: str
    run_id: str = ""
    session_id: str = ""
    operation_id: Optional[str] = None
    attempt_id: Optional[str] = None
    parent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    status: Optional[str] = None
    capability: Optional[str] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    integrity: EventIntegrity = EventIntegrity.VALID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "category": self.category,
            "source": self.source,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "operation_id": self.operation_id,
            "attempt_id": self.attempt_id,
            "parent_id": self.parent_id,
            "payload": self.payload,
            "status": self.status,
            "capability": self.capability,
            "duration": self.duration,
            "metadata": self.metadata,
            "integrity": self.integrity.value,
        }


@dataclass
class ReplayCheckpoint:
    """A checkpoint in the run."""
    checkpoint_id: str
    sequence: int
    timestamp: float
    state: Dict[str, Any] = field(default_factory=dict)
    label: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "state": self.state,
            "label": self.label,
            "metadata": self.metadata,
        }


@dataclass
class ReplaySnapshot:
    """A snapshot from the SnapshotManager."""
    snapshot_id: str
    run_id: str
    timestamp: float
    state: Dict[str, Any] = field(default_factory=dict)
    label: str = ""
    sequence: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "state": self.state,
            "label": self.label,
            "sequence": self.sequence,
        }


@dataclass
class SecurityDecision:
    """A security decision from the audit trail."""
    decision_id: str
    timestamp: float
    capability: str
    risk_level: str
    decision: str  # allowed, denied, approval_requested
    reason: str = ""
    source: str = ""
    run_id: str = ""
    sequence: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "capability": self.capability,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
            "source": self.source,
            "run_id": self.run_id,
            "sequence": self.sequence,
        }


@dataclass
class RecoveryAction:
    """A recovery action."""
    action_id: str
    timestamp: float
    failure_class: str
    strategy: str
    attempt_number: int
    budget_before: int
    budget_after: int
    success: bool
    run_id: str = ""
    sequence: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "timestamp": self.timestamp,
            "failure_class": self.failure_class,
            "strategy": self.strategy,
            "attempt_number": self.attempt_number,
            "budget_before": self.budget_before,
            "budget_after": self.budget_after,
            "success": self.success,
            "run_id": self.run_id,
            "sequence": self.sequence,
        }


@dataclass
class VerificationResult:
    """A verification result."""
    result_id: str
    timestamp: float
    criteria_name: str
    passed: bool
    confidence: float = 0.0
    details: str = ""
    run_id: str = ""
    sequence: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "timestamp": self.timestamp,
            "criteria_name": self.criteria_name,
            "passed": self.passed,
            "confidence": self.confidence,
            "details": self.details,
            "run_id": self.run_id,
            "sequence": self.sequence,
        }


@dataclass
class ReviewResult:
    """A review result."""
    result_id: str
    timestamp: float
    status: str
    findings_count: int = 0
    criteria_passed: int = 0
    criteria_failed: int = 0
    summary: str = ""
    run_id: str = ""
    sequence: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "findings_count": self.findings_count,
            "criteria_passed": self.criteria_passed,
            "criteria_failed": self.criteria_failed,
            "summary": self.summary,
            "run_id": self.run_id,
            "sequence": self.sequence,
        }


@dataclass
class ReplayRun:
    """A complete replayable run."""
    run_id: str
    session_id: str = ""
    task: str = ""
    started_at: float = 0.0
    ended_at: Optional[float] = None
    status: RunStatus = RunStatus.COMPLETE
    events: List[ReplayEvent] = field(default_factory=list)
    snapshots: List[ReplaySnapshot] = field(default_factory=list)
    checkpoints: List[ReplayCheckpoint] = field(default_factory=list)
    initial_state: Dict[str, Any] = field(default_factory=dict)
    final_state: Dict[str, Any] = field(default_factory=dict)
    security_decisions: List[SecurityDecision] = field(default_factory=list)
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    verification_results: List[VerificationResult] = field(default_factory=list)
    review_results: List[ReviewResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    integrity_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return None

    @property
    def event_count(self) -> int:
        return len(self.events)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "task": self.task,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": self.duration,
            "status": self.status.value,
            "event_count": self.event_count,
            "events": [e.to_dict() for e in self.events],
            "snapshots": [s.to_dict() for s in self.snapshots],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "security_decisions": [d.to_dict() for d in self.security_decisions],
            "recovery_actions": [a.to_dict() for a in self.recovery_actions],
            "verification_results": [v.to_dict() for v in self.verification_results],
            "review_results": [r.to_dict() for r in self.review_results],
            "metadata": self.metadata,
            "integrity_issues": self.integrity_issues,
            "warnings": self.warnings,
        }


@dataclass
class TimelineEntry:
    """An entry in the replay timeline."""
    sequence: int
    timestamp: float
    event_type: str
    category: str
    source: str
    status: Optional[str] = None
    capability: Optional[str] = None
    duration: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "category": self.category,
            "source": self.source,
            "status": self.status,
            "capability": self.capability,
            "duration": self.duration,
            "description": self.description,
        }


@dataclass
class ExecutionNode:
    """A node in the execution tree."""
    node_id: str
    event_type: str
    category: str
    source: str
    timestamp: float
    status: Optional[str] = None
    capability: Optional[str] = None
    children: List["ExecutionNode"] = field(default_factory=list)
    parent_id: Optional[str] = None
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "event_type": self.event_type,
            "category": self.category,
            "source": self.source,
            "timestamp": self.timestamp,
            "status": self.status,
            "capability": self.capability,
            "children": [c.to_dict() for c in self.children],
            "parent_id": self.parent_id,
            "sequence": self.sequence,
        }


@dataclass
class StateDiff:
    """Difference between two states."""
    files_added: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    plan_changes: List[str] = field(default_factory=list)
    assumption_changes: List[str] = field(default_factory=list)
    learned_facts_added: List[str] = field(default_factory=list)
    verification_changes: List[str] = field(default_factory=list)
    recovery_changes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_added": self.files_added,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
            "plan_changes": self.plan_changes,
            "assumption_changes": self.assumption_changes,
            "learned_facts_added": self.learned_facts_added,
            "verification_changes": self.verification_changes,
            "recovery_changes": self.recovery_changes,
        }


@dataclass
class ConsistencyIssue:
    """A consistency issue found during replay."""
    issue_id: str
    severity: str  # error, warning
    description: str
    event_sequence: Optional[int] = None
    related_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity,
            "description": self.description,
            "event_sequence": self.event_sequence,
            "related_events": self.related_events,
        }
