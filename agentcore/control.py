"""
ControlResult — outcome of a Hermes Desktop control operation.

Outcomes:
    ACCEPTED         — control request was accepted by Hermes
    COMPLETED_ALREADY — task was already in a terminal state
    NOT_FOUND        — Hermes execution or Argus task not found
    REJECTED         — Hermes rejected the control request
    FAILED           — control request failed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ControlResult:
    outcome: str
    message: str = ""
    hermes_status: str | None = None
    argus_task_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.outcome == "ACCEPTED"

    @property
    def completed_already(self) -> bool:
        return self.outcome == "COMPLETED_ALREADY"

    @property
    def not_found(self) -> bool:
        return self.outcome == "NOT_FOUND"

    @property
    def rejected(self) -> bool:
        return self.outcome == "REJECTED"

    @property
    def failed(self) -> bool:
        return self.outcome == "FAILED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "message": self.message,
            "hermes_status": self.hermes_status,
            "argus_task_id": self.argus_task_id,
            "details": self.details,
        }
