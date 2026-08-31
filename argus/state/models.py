"""State models for ARGUS agent."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class PlanStep:
    """A single step in the plan."""
    id: str
    description: str
    capability_id: str = ""
    status: str = "pending"  # pending, active, completed, failed
    input_data: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "capability_id": self.capability_id,
            "status": self.status,
            "input_data": self.input_data,
            "error": self.error,
        }


@dataclass
class AgentState:
    """Durable agent state for a run."""

    # Identifiers
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str = ""

    # Task
    task: str = ""
    status: RunStatus = RunStatus.PENDING
    current_phase: str = ""

    # Plan
    plan: List[PlanStep] = field(default_factory=list)
    current_step_id: Optional[str] = None

    # Reasoning
    assumptions: Dict[str, bool] = field(default_factory=dict)
    learned_facts: List[str] = field(default_factory=list)

    # Execution
    selected_capabilities: List[str] = field(default_factory=list)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)

    # Verification
    verification_results: List[Dict[str, Any]] = field(default_factory=list)

    # Recovery
    recovery_state: Dict[str, Any] = field(default_factory=dict)
    recovery_budget: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    # Context
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "task": self.task,
            "status": self.status.value,
            "current_phase": self.current_phase,
            "plan": [s.to_dict() for s in self.plan],
            "current_step_id": self.current_step_id,
            "assumptions": self.assumptions,
            "learned_facts": self.learned_facts,
            "selected_capabilities": self.selected_capabilities,
            "execution_history": self.execution_history,
            "verification_results": self.verification_results,
            "recovery_state": self.recovery_state,
            "recovery_budget": self.recovery_budget,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        plan = [
            PlanStep(
                id=s.get("id", str(uuid.uuid4())[:6]),
                description=s.get("description", ""),
                capability_id=s.get("capability_id", ""),
                status=s.get("status", "pending"),
                input_data=s.get("input_data", {}),
                error=s.get("error"),
            )
            for s in data.get("plan", [])
        ]

        return cls(
            run_id=data.get("run_id", str(uuid.uuid4())[:8]),
            session_id=data.get("session_id", str(uuid.uuid4())[:8]),
            project_id=data.get("project_id", ""),
            task=data.get("task", ""),
            status=RunStatus(data.get("status", "pending")),
            current_phase=data.get("current_phase", ""),
            plan=plan,
            current_step_id=data.get("current_step_id"),
            assumptions=data.get("assumptions", {}),
            learned_facts=data.get("learned_facts", []),
            selected_capabilities=data.get("selected_capabilities", []),
            execution_history=data.get("execution_history", []),
            verification_results=data.get("verification_results", []),
            recovery_state=data.get("recovery_state", {}),
            recovery_budget=data.get("recovery_budget", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            completed_at=data.get("completed_at"),
            context=data.get("context", {}),
        )

    @property
    def current_step(self) -> Optional[PlanStep]:
        for step in self.plan:
            if step.id == self.current_step_id:
                return step
        return None

    @property
    def completed_steps(self) -> List[PlanStep]:
        return [s for s in self.plan if s.status == "completed"]

    @property
    def failed_steps(self) -> List[PlanStep]:
        return [s for s in self.plan if s.status == "failed"]

    @property
    def progress(self) -> float:
        if not self.plan:
            return 0.0
        return len(self.completed_steps) / len(self.plan)

    def update(self) -> None:
        self.updated_at = time.time()

    def complete(self) -> None:
        self.status = RunStatus.COMPLETED
        self.completed_at = time.time()
        self.update()

    def fail(self) -> None:
        self.status = RunStatus.FAILED
        self.completed_at = time.time()
        self.update()

    def add_plan_step(self, description: str, capability_id: str = "", input_data: Dict[str, Any] = None) -> PlanStep:
        step = PlanStep(
            id=str(uuid.uuid4())[:6],
            description=description,
            capability_id=capability_id,
            input_data=input_data or {},
        )
        self.plan.append(step)
        self.update()
        return step

    def set_step_status(self, step_id: str, status: str, output: Any = None, error: Optional[str] = None) -> None:
        for step in self.plan:
            if step.id == step_id:
                step.status = status
                if output is not None:
                    step.output = output
                if error is not None:
                    step.error = error
                break
        self.update()

    def add_assumption(self, assumption: str, valid: bool = True) -> None:
        self.assumptions[assumption] = valid
        self.update()

    def invalidate_assumption(self, assumption: str) -> None:
        if assumption in self.assumptions:
            self.assumptions[assumption] = False
        self.update()

    def add_learned_fact(self, fact: str) -> None:
        if fact not in self.learned_facts:
            self.learned_facts.append(fact)
        self.update()

    def add_execution_record(self, record: Dict[str, Any]) -> None:
        record["timestamp"] = time.time()
        self.execution_history.append(record)
        self.update()

    def add_verification_result(self, result: Dict[str, Any]) -> None:
        result["timestamp"] = time.time()
        self.verification_results.append(result)
        self.update()

    def set_recovery_state(self, state: Dict[str, Any]) -> None:
        self.recovery_state = state
        self.update()

    def set_recovery_budget(self, budget: Dict[str, Any]) -> None:
        self.recovery_budget = budget
        self.update()