from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class TaskState(Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    ROUTING = "ROUTING"
    INVESTIGATING = "INVESTIGATING"
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    user_request: str = ""
    project: str = ""
    selected_skills: List[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    project_context: dict[str, Any] = field(default_factory=dict)
    memory_context: dict[str, Any] = field(default_factory=dict)
    current_state: TaskState = TaskState.CREATED
    plan: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    changes: List[Dict[str, Any]] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def update_state(self, state: TaskState) -> None:
        self.current_state = state
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
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
    def from_dict(cls, data: dict[str, Any]) -> "Hypothesis":
        return cls(
            statement=data["statement"],
            supporting_evidence=data["supporting_evidence"],
            contradicting_evidence=data["contradicting_evidence"],
            status=data["status"],
        )