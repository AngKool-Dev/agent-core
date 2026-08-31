"""Verification result types for ARGUS."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class CriterionResult:
    """Result of a single verification criterion."""
    name: str
    status: VerificationStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration": self.duration,
        }


@dataclass
class VerificationResult:
    """Complete verification result."""
    status: VerificationStatus
    criteria: List[CriterionResult] = field(default_factory=list)
    confidence: float = 0.0
    message: str = ""
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED

    @property
    def failed_criteria(self) -> List[CriterionResult]:
        return [c for c in self.criteria if c.status == VerificationStatus.FAILED]

    @property
    def passed_criteria(self) -> List[CriterionResult]:
        return [c for c in self.criteria if c.status == VerificationStatus.PASSED]

    @property
    def pass_rate(self) -> float:
        if not self.criteria:
            return 0.0
        return len(self.passed_criteria) / len(self.criteria)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "criteria": [c.to_dict() for c in self.criteria],
            "confidence": self.confidence,
            "message": self.message,
            "duration": self.duration,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        criteria = [
            CriterionResult(
                name=c["name"],
                status=VerificationStatus(c["status"]),
                message=c.get("message", ""),
                details=c.get("details", {}),
                duration=c.get("duration", 0.0),
            )
            for c in data.get("criteria", [])
        ]
        return cls(
            status=VerificationStatus(data.get("status", "error")),
            criteria=criteria,
            confidence=data.get("confidence", 0.0),
            message=data.get("message", ""),
            duration=data.get("duration", 0.0),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def all_passed(cls, criteria: List[CriterionResult], message: str = "All checks passed") -> "VerificationResult":
        return cls(
            status=VerificationStatus.PASSED,
            criteria=criteria,
            confidence=1.0,
            message=message,
        )

    @classmethod
    def with_failures(cls, criteria: List[CriterionResult], message: str = "Some checks failed") -> "VerificationResult":
        has_failure = any(c.status == VerificationStatus.FAILED for c in criteria)
        return cls(
            status=VerificationStatus.FAILED if has_failure else VerificationStatus.PASSED,
            criteria=criteria,
            confidence=sum(1 for c in criteria if c.passed) / len(criteria) if criteria else 0.0,
            message=message,
        )