"""Subagent models for ARGUS."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SubagentStatus(str, Enum):
    """Subagent lifecycle statuses."""
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"


class SubagentRole(str, Enum):
    """Subagent roles."""
    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    TESTER = "tester"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"


@dataclass(frozen=True)
class SubagentId:
    """Typed subagent identifier."""
    value: str

    @classmethod
    def generate(cls) -> "SubagentId":
        return cls(value=str(uuid.uuid4())[:8])

    def __str__(self) -> str:
        return self.value


@dataclass
class Subagent:
    """A bounded worker subagent."""
    id: SubagentId = field(default_factory=SubagentId.generate)
    parent_run_id: str = ""
    parent_task_id: str = ""
    role: SubagentRole = SubagentRole.RESEARCHER
    objective: str = ""
    status: SubagentStatus = SubagentStatus.CREATED

    # Scopes
    capability_scope: List[str] = field(default_factory=list)
    path_scope: List[str] = field(default_factory=list)
    command_scope: List[str] = field(default_factory=list)

    # Model
    model: str = ""

    # Budget
    budget: Dict[str, int] = field(default_factory=dict)
    budget_used: Dict[str, int] = field(default_factory=dict)

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Result
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Hierarchy
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "parent_run_id": self.parent_run_id,
            "parent_task_id": self.parent_task_id,
            "role": self.role.value,
            "objective": self.objective,
            "status": self.status.value,
            "capability_scope": self.capability_scope,
            "path_scope": self.path_scope,
            "command_scope": self.command_scope,
            "model": self.model,
            "budget": self.budget,
            "budget_used": self.budget_used,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
        }

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        if self.started_at:
            return time.time() - self.started_at
        return None

    @property
    def is_active(self) -> bool:
        return self.status in (SubagentStatus.QUEUED, SubagentStatus.RUNNING, SubagentStatus.PAUSED)

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            SubagentStatus.COMPLETED,
            SubagentStatus.FAILED,
            SubagentStatus.CANCELLED,
            SubagentStatus.TIMED_OUT,
            SubagentStatus.BLOCKED,
        )


@dataclass(frozen=True)
class SubagentTask:
    """A task delegated to a subagent."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_run_id: str = ""
    parent_task_id: str = ""
    objective: str = ""
    role: SubagentRole = SubagentRole.RESEARCHER
    inputs: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    required_output: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    deadline: Optional[float] = None
    budget: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "parent_run_id": self.parent_run_id,
            "parent_task_id": self.parent_task_id,
            "objective": self.objective,
            "role": self.role.value,
            "inputs": self.inputs,
            "constraints": self.constraints,
            "required_output": self.required_output,
            "priority": self.priority,
            "deadline": self.deadline,
            "budget": self.budget,
        }


@dataclass(frozen=True)
class SubagentResult:
    """Result from a subagent."""
    task_id: str = ""
    subagent_id: str = ""
    status: SubagentStatus = SubagentStatus.COMPLETED
    summary: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    recommendations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration: Optional[float] = None
    budget_usage: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "subagent_id": self.subagent_id,
            "status": self.status.value,
            "summary": self.summary,
            "findings": self.findings,
            "artifacts": self.artifacts,
            "evidence": self.evidence,
            "verification": self.verification,
            "recommendations": self.recommendations,
            "errors": self.errors,
            "duration": self.duration,
            "budget_usage": self.budget_usage,
        }

    @property
    def is_success(self) -> bool:
        return self.status == SubagentStatus.COMPLETED

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


# Valid state transitions
VALID_TRANSITIONS: Dict[SubagentStatus, List[SubagentStatus]] = {
    SubagentStatus.CREATED: [SubagentStatus.QUEUED, SubagentStatus.CANCELLED],
    SubagentStatus.QUEUED: [SubagentStatus.RUNNING, SubagentStatus.CANCELLED],
    SubagentStatus.RUNNING: [
        SubagentStatus.PAUSED,
        SubagentStatus.COMPLETED,
        SubagentStatus.FAILED,
        SubagentStatus.CANCELLED,
        SubagentStatus.TIMED_OUT,
        SubagentStatus.BLOCKED,
    ],
    SubagentStatus.PAUSED: [SubagentStatus.RUNNING, SubagentStatus.CANCELLED],
    SubagentStatus.COMPLETED: [],
    SubagentStatus.FAILED: [],
    SubagentStatus.CANCELLED: [],
    SubagentStatus.TIMED_OUT: [],
    SubagentStatus.BLOCKED: [],
}


def is_valid_transition(from_status: SubagentStatus, to_status: SubagentStatus) -> bool:
    """Check if a state transition is valid."""
    valid = VALID_TRANSITIONS.get(from_status, [])
    return to_status in valid
