"""Recovery state - tracks state across recovery attempts."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.recovery.result import FailureEvidence, RecoveryAction


@dataclass
class AttemptRecord:
    """Record of a single attempt."""
    attempt_number: int
    capability_id: str
    input_data: Dict[str, Any]
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "capability_id": self.capability_id,
            "success": self.success,
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp,
        }


@dataclass
class RecoveryState:
    """State maintained during recovery."""

    task: str
    current_plan: List[str] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    attempts: List[AttemptRecord] = field(default_factory=list)
    failures: List[FailureEvidence] = field(default_factory=list)
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    assumptions: Dict[str, bool] = field(default_factory=dict)
    learned_facts: List[str] = field(default_factory=list)
    start_time: float = 0.0

    def __post_init__(self):
        if self.start_time == 0.0:
            self.start_time = time.time()

    def add_attempt(self, attempt: AttemptRecord) -> None:
        self.attempts.append(attempt)

    def add_failure(self, failure: FailureEvidence) -> None:
        self.failures.append(failure)

    def add_recovery_action(self, action: RecoveryAction) -> None:
        self.recovery_actions.append(action)

    def mark_step_completed(self, step: str) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    def mark_step_failed(self, step: str) -> None:
        if step not in self.failed_steps:
            self.failed_steps.append(step)

    def add_assumption(self, assumption: str, valid: bool = True) -> None:
        self.assumptions[assumption] = valid

    def invalidate_assumption(self, assumption: str) -> None:
        if assumption in self.assumptions:
            self.assumptions[assumption] = False

    def add_learned_fact(self, fact: str) -> None:
        if fact not in self.learned_facts:
            self.learned_facts.append(fact)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def last_failure(self) -> Optional[FailureEvidence]:
        return self.failures[-1] if self.failures else None

    @property
    def last_attempt(self) -> Optional[AttemptRecord]:
        return self.attempts[-1] if self.attempts else None

    @property
    def invalid_assumptions(self) -> List[str]:
        return [a for a, v in self.assumptions.items() if not v]

    @property
    def common_failure_class(self) -> Optional[str]:
        if not self.failures:
            return None
        from collections import Counter
        classes = [f.failure_class.value for f in self.failures]
        return Counter(classes).most_common(1)[0][0]

    def get_changed_assumptions(self) -> List[str]:
        """Get assumptions that were invalidated."""
        return self.invalid_assumptions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "current_plan": self.current_plan,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "attempt_count": self.attempt_count,
            "failure_count": self.failure_count,
            "assumptions": self.assumptions,
            "learned_facts": self.learned_facts,
            "common_failure_class": self.common_failure_class,
        }