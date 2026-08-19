from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any


class TaskState(Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    ROUTING = "ROUTING"
    INVESTIGATING = "INVESTIGATING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    OBSERVING = "OBSERVING"
    REPLANNING = "REPLANNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    IMPLEMENTING = "IMPLEMENTING"


_VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {
        TaskState.ANALYZING,
        TaskState.CANCELLED,
        TaskState.FAILED,
    },
    TaskState.ANALYZING: {
        TaskState.ROUTING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.ROUTING: {
        TaskState.INVESTIGATING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.INVESTIGATING: {
        TaskState.PLANNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.PLANNING: {
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.RUNNING: {
        TaskState.WAITING_FOR_TOOL,
        TaskState.VERIFYING,
        TaskState.REPLANNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.IMPLEMENTING: {
        TaskState.WAITING_FOR_TOOL,
        TaskState.VERIFYING,
        TaskState.REPLANNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.WAITING_FOR_TOOL: {
        TaskState.OBSERVING,
        TaskState.CANCELLED,
        TaskState.FAILED,
    },
    TaskState.OBSERVING: {
        TaskState.RUNNING,
        TaskState.REPLANNING,
        TaskState.VERIFYING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.REPLANNING: {
        TaskState.PLANNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,
    },
    TaskState.VERIFYING: {
        TaskState.COMPLETED,
        TaskState.REPLANNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.COMPLETED: {
        TaskState.CANCELLED,
    },
    TaskState.FAILED: {
        TaskState.CANCELLED,
    },
    TaskState.CANCELLED: {
        TaskState.CANCELLED,
    },
    TaskState.BLOCKED: {
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
}

_TERMINAL_STATES = {
    TaskState.COMPLETED,
    TaskState.FAILED,
    TaskState.CANCELLED,
}


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class PlanStep:
    action: str
    description: str
    status: StepStatus = StepStatus.PENDING
    outcome: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, StepStatus) else self.status,
            "outcome": self.outcome,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        status = data.get("status", StepStatus.PENDING)
        if isinstance(status, str):
            status = StepStatus(status)
        return cls(
            action=data["action"],
            description=data["description"],
            status=status,
            outcome=data.get("outcome"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class InvalidStateTransitionError(Exception):
    def __init__(self, current: TaskState, target: TaskState):
        self.current = current
        self.target = target
        super().__init__(f"Invalid state transition: {current.value} -> {target.value}")


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    user_request: str = ""
    project: str = ""
    selected_skills: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    project_context: dict[str, Any] = field(default_factory=dict)
    memory_context: dict[str, Any] = field(default_factory=dict)
    current_state: TaskState = TaskState.CREATED
    plan: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def transition(self, new_state: TaskState, reason: str = "") -> None:
        if self.current_state in _TERMINAL_STATES and new_state not in _TERMINAL_STATES:
            raise InvalidStateTransitionError(self.current_state, new_state)

        allowed = _VALID_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(self.current_state, new_state)

        self.current_state = new_state
        self.updated_at = datetime.now(UTC).isoformat()

    def update_state(self, state: TaskState) -> None:
        self.current_state = state
        self.updated_at = datetime.now(UTC).isoformat()

    def _select_next_step(self, plan: list[PlanStep]) -> PlanStep | None:
        for step in plan:
            status = step.status
            if isinstance(status, str):
                status = StepStatus(status)
            if status == StepStatus.PENDING:
                return step
        return None

    def is_terminal(self) -> bool:
        return self.current_state in _TERMINAL_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_request": self.user_request,
            "project": self.project,
            "selected_skills": self.selected_skills,
            "attributes": self.attributes,
            "project_context": self.project_context,
            "memory_context": self.memory_context,
            "current_state": self.current_state.value,
            "plan": self.plan,
            "actions": self.actions,
            "tool_results": self.tool_results,
            "changes": self.changes,
            "test_results": self.test_results,
            "verification": self.verification,
            "errors": self.errors,
            "hypotheses": self.hypotheses,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            task_id=data["task_id"],
            user_request=data["user_request"],
            project=data["project"],
            selected_skills=data["selected_skills"],
            attributes=data.get("attributes", {}),
            project_context=data["project_context"],
            memory_context=data["memory_context"],
            current_state=TaskState(data["current_state"]),
            plan=data["plan"],
            actions=data["actions"],
            tool_results=data["tool_results"],
            changes=data["changes"],
            test_results=data["test_results"],
            verification=data["verification"],
            errors=data["errors"],
            hypotheses=data["hypotheses"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass
class Hypothesis:
    statement: str
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    status: str = "PROPOSED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hypothesis:
        return cls(
            statement=data["statement"],
            supporting_evidence=data["supporting_evidence"],
            contradicting_evidence=data["contradicting_evidence"],
            status=data["status"],
        )
