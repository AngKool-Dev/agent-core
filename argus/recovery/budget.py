"""Recovery budget - finite envelope for recovery attempts."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class RecoveryBudget:
    """Budget for recovery attempts."""

    max_attempts: int = 10
    max_retries: int = 3
    max_replans: int = 3
    max_backend_switches: int = 2
    max_repair_cycles: int = 4
    time_budget_seconds: float = 600.0  # 10 minutes

    # Current usage
    attempts: int = 0
    retries: int = 0
    replans: int = 0
    backend_switches: int = 0
    repair_cycles: int = 0
    start_time: float = 0.0

    def __post_init__(self):
        if self.start_time == 0.0:
            self.start_time = time.time()

    @property
    def time_elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def time_remaining(self) -> float:
        return max(0.0, self.time_budget_seconds - self.time_elapsed)

    @property
    def exhausted(self) -> bool:
        return (
            self.attempts >= self.max_attempts
            or self.time_remaining <= 0
        )

    @property
    def can_retry(self) -> bool:
        return (
            self.retries < self.max_retries
            and self.attempts < self.max_attempts
            and self.time_remaining > 0
        )

    @property
    def can_replan(self) -> bool:
        return (
            self.replans < self.max_replans
            and self.attempts < self.max_attempts
            and self.time_remaining > 0
        )

    @property
    def can_switch_backend(self) -> bool:
        return (
            self.backend_switches < self.max_backend_switches
            and self.attempts < self.max_attempts
            and self.time_remaining > 0
        )

    @property
    def can_repair(self) -> bool:
        return (
            self.repair_cycles < self.max_repair_cycles
            and self.attempts < self.max_attempts
            and self.time_remaining > 0
        )

    def consume_attempt(self) -> None:
        self.attempts += 1

    def consume_retry(self) -> None:
        self.retries += 1
        self.attempts += 1

    def consume_replan(self) -> None:
        self.replans += 1
        self.attempts += 1

    def consume_backend_switch(self) -> None:
        self.backend_switches += 1
        self.attempts += 1

    def consume_repair(self) -> None:
        self.repair_cycles += 1
        self.attempts += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempts": f"{self.attempts}/{self.max_attempts}",
            "retries": f"{self.retries}/{self.max_retries}",
            "replans": f"{self.replans}/{self.max_replans}",
            "backend_switches": f"{self.backend_switches}/{self.max_backend_switches}",
            "repair_cycles": f"{self.repair_cycles}/{self.max_repair_cycles}",
            "time": f"{self.time_elapsed:.0f}s/{self.time_budget_seconds:.0f}s",
            "exhausted": self.exhausted,
        }

    def summary(self) -> str:
        return (
            f"Attempts {self.attempts}/{self.max_attempts} | "
            f"Retries {self.retries}/{self.max_retries} | "
            f"Replans {self.replans}/{self.max_replans} | "
            f"Backend {self.backend_switches}/{self.max_backend_switches} | "
            f"Repair {self.repair_cycles}/{self.max_repair_cycles} | "
            f"Time {self.time_elapsed:.0f}s/{self.time_budget_seconds:.0f}s"
        )

    @classmethod
    def default(cls) -> "RecoveryBudget":
        return cls()

    @classmethod
    def aggressive(cls) -> "RecoveryBudget":
        return cls(
            max_attempts=15,
            max_retries=5,
            max_replans=5,
            max_backend_switches=3,
            max_repair_cycles=6,
            time_budget_seconds=900.0,
        )

    @classmethod
    def conservative(cls) -> "RecoveryBudget":
        return cls(
            max_attempts=5,
            max_retries=2,
            max_replans=2,
            max_backend_switches=1,
            max_repair_cycles=2,
            time_budget_seconds=300.0,
        )