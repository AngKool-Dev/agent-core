"""Review models for ARGUS."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewStatus(str, Enum):
    """Final review status."""
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    FAIL = "fail"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"


class ReviewSeverity(str, Enum):
    """Severity of a review finding."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    """Category of a review finding."""
    REQUIREMENT = "requirement"
    VERIFICATION = "verification"
    REGRESSION = "regression"
    SECURITY = "security"
    QUALITY = "quality"
    SCOPE = "scope"
    DIFF = "diff"
    TEST_DELETION = "test_deletion"
    CONSISTENCY = "consistency"


class CriterionStatus(str, Enum):
    """Status of a review criterion."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ReviewFinding:
    """A single finding from the review."""
    category: FindingCategory
    severity: ReviewSeverity
    summary: str
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    file: Optional[str] = None
    line: Optional[int] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "detail": self.detail,
            "evidence": self.evidence,
            "file": self.file,
            "line": self.line,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class CriterionResult:
    """Result of evaluating a single review criterion."""
    criterion: str
    status: CriterionStatus
    severity: ReviewSeverity = ReviewSeverity.INFO
    summary: str = ""
    findings: List[ReviewFinding] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion,
            "status": self.status.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ReviewResult:
    """Complete review result."""
    status: ReviewStatus
    criteria: List[CriterionResult] = field(default_factory=list)
    findings: List[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    task: str = ""
    run_id: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    review_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_critical_findings(self) -> bool:
        return any(f.severity == ReviewSeverity.CRITICAL for f in self.findings)

    @property
    def has_high_findings(self) -> bool:
        return any(f.severity == ReviewSeverity.HIGH for f in self.findings)

    @property
    def has_security_findings(self) -> bool:
        return any(f.category == FindingCategory.SECURITY for f in self.findings)

    @property
    def failed_criteria(self) -> List[CriterionResult]:
        return [c for c in self.criteria if c.status == CriterionStatus.FAIL]

    @property
    def warning_criteria(self) -> List[CriterionResult]:
        return [c for c in self.criteria if c.status == CriterionStatus.WARNING]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "status": self.status.value,
            "summary": self.summary,
            "task": self.task,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "criteria": [c.to_dict() for c in self.criteria],
            "findings": [f.to_dict() for f in self.findings],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, default=str)


@dataclass(frozen=True)
class ReviewEvidence:
    """Evidence collected for review."""
    source: str
    evidence_type: str
    timestamp: float = field(default_factory=time.time)
    run_id: str = ""
    reliability: float = 1.0
    summary: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "evidence_type": self.evidence_type,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "reliability": self.reliability,
            "summary": self.summary,
            "data": self.data,
        }


@dataclass
class EvidenceCollection:
    """Collection of evidence for review."""
    evidence: List[ReviewEvidence] = field(default_factory=list)

    def add(self, evidence: ReviewEvidence) -> None:
        self.evidence.append(evidence)

    def get_by_type(self, evidence_type: str) -> List[ReviewEvidence]:
        return [e for e in self.evidence if e.evidence_type == evidence_type]

    def get_by_source(self, source: str) -> List[ReviewEvidence]:
        return [e for e in self.evidence if e.source == source]

    def has_type(self, evidence_type: str) -> bool:
        return any(e.evidence_type == evidence_type for e in self.evidence)

    def has_source(self, source: str) -> bool:
        return any(e.source == source for e in self.evidence)

    @property
    def types(self) -> List[str]:
        return list(set(e.evidence_type for e in self.evidence))

    @property
    def sources(self) -> List[str]:
        return list(set(e.source for e in self.evidence))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_count": len(self.evidence),
            "types": self.types,
            "sources": self.sources,
            "evidence": [e.to_dict() for e in self.evidence],
        }
