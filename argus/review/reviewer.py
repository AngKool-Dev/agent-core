"""Review engine orchestrator for ARGUS."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.events import EventEmitter, EventSource, EventStatus, EventType
from argus.review.criteria import (
    DiffQualityCriterion,
    RegressionCriterion,
    RequirementCriterion,
    ReviewCriterion,
    ScopeCriterion,
    SecurityCriterion,
    TestDeletionCriterion,
    VerificationCriterion,
)
from argus.review.evidence import EvidenceCollector
from argus.review.models import (
    CriterionResult,
    CriterionStatus,
    EvidenceCollection,
    FindingCategory,
    ReviewEvidence,
    ReviewFinding,
    ReviewResult,
    ReviewSeverity,
    ReviewStatus,
)


class ReviewEngine:
    """Orchestrates review criteria and produces a ReviewResult."""

    def __init__(self, criteria: Optional[List[ReviewCriterion]] = None,
                 event_emitter: Optional[EventEmitter] = None):
        self._criteria = criteria or self._default_criteria()
        self._pre_review_hooks: List[Callable] = []
        self._post_review_hooks: List[Callable] = []
        self._event_emitter = event_emitter

    @property
    def criteria(self) -> List[ReviewCriterion]:
        return list(self._criteria)

    def add_criterion(self, criterion: ReviewCriterion) -> None:
        """Add a review criterion."""
        self._criteria.append(criterion)

    def remove_criterion(self, name: str) -> bool:
        """Remove a criterion by name."""
        for i, c in enumerate(self._criteria):
            if c.name == name:
                self._criteria.pop(i)
                return True
        return False

    def _default_criteria(self) -> List[ReviewCriterion]:
        """Get default review criteria."""
        return [
            RequirementCriterion(),
            VerificationCriterion(),
            RegressionCriterion(),
            SecurityCriterion(),
            DiffQualityCriterion(),
            ScopeCriterion(),
            TestDeletionCriterion(),
        ]

    def review(
        self,
        evidence: EvidenceCollection,
        task: str = "",
        run_id: str = "",
        session_id: str = "",
    ) -> ReviewResult:
        """Run the review and produce a ReviewResult."""
        start_time = time.time()

        # Emit review started event
        if self._event_emitter:
            self._event_emitter.emit(
                EventType.VERIFICATION_STARTED,
                EventSource.VERIFICATION_ENGINE,
                status=EventStatus.STARTED,
                metadata={"criteria_count": len(self._criteria)},
            )

        # Run pre-review hooks
        for hook in self._pre_review_hooks:
            hook(evidence)

        # Evaluate each criterion
        criterion_results = []
        all_findings = []

        for criterion in self._criteria:
            try:
                result = criterion.evaluate(evidence)
                criterion_results.append(result)
                all_findings.extend(result.findings)

                # Emit criterion completed event
                if self._event_emitter:
                    self._event_emitter.emit(
                        EventType.VERIFICATION_CRITERION_COMPLETED,
                        EventSource.VERIFICATION_ENGINE,
                        status=EventStatus.COMPLETED if result.status == CriterionStatus.PASS else EventStatus.FAILED,
                        metadata={
                            "criterion": criterion.name,
                            "status": result.status.value,
                        },
                    )
            except Exception as e:
                # Criterion evaluation failed - record as inconclusive
                criterion_results.append(CriterionResult(
                    criterion=criterion.name,
                    status=CriterionStatus.INCONCLUSIVE,
                    severity=ReviewSeverity.INFO,
                    summary=f"Criterion evaluation failed: {str(e)}",
                    evidence={"error": str(e)},
                    confidence=0.0,
                ))

                if self._event_emitter:
                    self._event_emitter.emit(
                        EventType.VERIFICATION_CRITERION_COMPLETED,
                        EventSource.VERIFICATION_ENGINE,
                        status=EventStatus.FAILED,
                        metadata={"criterion": criterion.name, "error": str(e)},
                    )

        # Determine final status
        status = self._aggregate_status(criterion_results, all_findings)

        # Generate summary
        summary = self._generate_summary(status, criterion_results, all_findings)

        duration = time.time() - start_time

        result = ReviewResult(
            status=status,
            criteria=criterion_results,
            findings=all_findings,
            summary=summary,
            task=task,
            run_id=run_id,
            session_id=session_id,
            duration=duration,
        )

        # Emit review completed event
        if self._event_emitter:
            self._event_emitter.emit(
                EventType.VERIFICATION_COMPLETED,
                EventSource.VERIFICATION_ENGINE,
                status=EventStatus.COMPLETED if status in (ReviewStatus.PASS, ReviewStatus.PASS_WITH_WARNINGS) else EventStatus.FAILED,
                metadata={
                    "review_status": status.value,
                    "findings_count": len(all_findings),
                    "duration": duration,
                },
            )

        # Run post-review hooks
        for hook in self._post_review_hooks:
            hook(result)

        return result

    def _aggregate_status(
        self,
        criteria: List[CriterionResult],
        findings: List[ReviewFinding],
    ) -> ReviewStatus:
        """Aggregate criterion results into a final status."""
        # Critical findings always result in BLOCKED
        if any(f.severity == ReviewSeverity.CRITICAL for f in findings):
            return ReviewStatus.BLOCKED

        # High security findings result in BLOCKED
        security_findings = [f for f in findings if f.category == FindingCategory.SECURITY]
        if any(f.severity == ReviewSeverity.HIGH for f in security_findings):
            return ReviewStatus.BLOCKED

        # Check for failed criteria
        failed = [c for c in criteria if c.status == CriterionStatus.FAIL]
        warnings = [c for c in criteria if c.status == CriterionStatus.WARNING]
        inconclusive = [c for c in criteria if c.status == CriterionStatus.INCONCLUSIVE]
        passed = [c for c in criteria if c.status == CriterionStatus.PASS]
        evaluated = passed + failed + warnings  # Criteria that were actually evaluated

        # High severity failures result in FAIL
        high_failures = [c for c in failed if c.severity >= ReviewSeverity.HIGH]
        if high_failures:
            return ReviewStatus.FAIL

        # Any failures result in FAIL
        if failed:
            return ReviewStatus.FAIL

        # If we have passing criteria and only warnings, return PASS_WITH_WARNINGS
        if passed and warnings and not inconclusive:
            return ReviewStatus.PASS_WITH_WARNINGS

        # If we have passing criteria and warnings, return PASS_WITH_WARNINGS
        if passed and warnings:
            return ReviewStatus.PASS_WITH_WARNINGS

        # All evaluated criteria passed
        if passed and not inconclusive and not warnings:
            return ReviewStatus.PASS

        # Some pass, some inconclusive - if no failures or warnings
        if passed and inconclusive and not warnings and not failed:
            # If the inconclusive criteria are high severity, return INCONCLUSIVE
            high_inconclusive = [c for c in inconclusive if c.severity >= ReviewSeverity.HIGH]
            if high_inconclusive:
                return ReviewStatus.INCONCLUSIVE
            return ReviewStatus.PASS_WITH_WARNINGS

        # Only warnings
        if warnings:
            return ReviewStatus.PASS_WITH_WARNINGS

        # All inconclusive
        if inconclusive and not passed and not failed:
            return ReviewStatus.INCONCLUSIVE

        return ReviewStatus.INCONCLUSIVE

    def _generate_summary(
        self,
        status: ReviewStatus,
        criteria: List[CriterionResult],
        findings: List[ReviewFinding],
    ) -> str:
        """Generate a human-readable summary."""
        passed = sum(1 for c in criteria if c.status == CriterionStatus.PASS)
        failed = sum(1 for c in criteria if c.status == CriterionStatus.FAIL)
        warnings = sum(1 for c in criteria if c.status == CriterionStatus.WARNING)
        inconclusive = sum(1 for c in criteria if c.status == CriterionStatus.INCONCLUSIVE)

        parts = [f"Review {status.value}"]
        parts.append(f"{passed} criteria passed")

        if failed:
            parts.append(f"{failed} failed")
        if warnings:
            parts.append(f"{warnings} warnings")
        if inconclusive:
            parts.append(f"{inconclusive} inconclusive")

        if findings:
            critical = sum(1 for f in findings if f.severity == ReviewSeverity.CRITICAL)
            high = sum(1 for f in findings if f.severity == ReviewSeverity.HIGH)
            if critical:
                parts.append(f"{critical} critical findings")
            if high:
                parts.append(f"{high} high-severity findings")

        return ", ".join(parts)

    def add_pre_review_hook(self, hook: Callable) -> None:
        """Add a hook to run before review."""
        self._pre_review_hooks.append(hook)

    def add_post_review_hook(self, hook: Callable) -> None:
        """Add a hook to run after review."""
        self._post_review_hooks.append(hook)


def run_review(
    evidence: EvidenceCollection,
    task: str = "",
    run_id: str = "",
    session_id: str = "",
    criteria: Optional[List[ReviewCriterion]] = None,
    event_emitter: Optional[EventEmitter] = None,
) -> ReviewResult:
    """Convenience function to run a review."""
    engine = ReviewEngine(criteria=criteria, event_emitter=event_emitter)
    return engine.review(evidence, task=task, run_id=run_id, session_id=session_id)
