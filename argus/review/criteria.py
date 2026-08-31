"""Review criteria for ARGUS."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from argus.review.models import (
    CriterionResult,
    CriterionStatus,
    EvidenceCollection,
    FindingCategory,
    ReviewEvidence,
    ReviewFinding,
    ReviewSeverity,
)


class ReviewCriterion(ABC):
    """Base class for review criteria."""

    def __init__(self, name: str, category: FindingCategory,
                 severity: ReviewSeverity = ReviewSeverity.MEDIUM):
        self._name = name
        self._category = category
        self._severity = severity

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> FindingCategory:
        return self._category

    @property
    def severity(self) -> ReviewSeverity:
        return self._severity

    @abstractmethod
    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        """Evaluate the criterion against evidence."""
        pass

    def _pass(self, summary: str = "", evidence: Dict[str, Any] = None) -> CriterionResult:
        return CriterionResult(
            criterion=self._name,
            status=CriterionStatus.PASS,
            severity=ReviewSeverity.INFO,
            summary=summary or f"{self._name} passed",
            evidence=evidence or {},
        )

    def _fail(self, summary: str, findings: List[ReviewFinding] = None,
              evidence: Dict[str, Any] = None) -> CriterionResult:
        return CriterionResult(
            criterion=self._name,
            status=CriterionStatus.FAIL,
            severity=self._severity,
            summary=summary,
            findings=findings or [],
            evidence=evidence or {},
        )

    def _warning(self, summary: str, findings: List[ReviewFinding] = None,
                 evidence: Dict[str, Any] = None) -> CriterionResult:
        return CriterionResult(
            criterion=self._name,
            status=CriterionStatus.WARNING,
            severity=ReviewSeverity.LOW,
            summary=summary,
            findings=findings or [],
            evidence=evidence or {},
        )

    def _inconclusive(self, summary: str = "Insufficient evidence",
                      evidence: Dict[str, Any] = None) -> CriterionResult:
        return CriterionResult(
            criterion=self._name,
            status=CriterionStatus.INCONCLUSIVE,
            severity=ReviewSeverity.INFO,
            summary=summary,
            evidence=evidence or {},
            confidence=0.0,
        )

    def _skipped(self, summary: str = "Criterion skipped",
                 evidence: Dict[str, Any] = None) -> CriterionResult:
        return CriterionResult(
            criterion=self._name,
            status=CriterionStatus.SKIPPED,
            severity=ReviewSeverity.INFO,
            summary=summary,
            evidence=evidence or {},
        )


class RequirementCriterion(ReviewCriterion):
    """Checks whether requirements are satisfied."""

    def __init__(self):
        super().__init__(
            name="requirement_satisfaction",
            category=FindingCategory.REQUIREMENT,
            severity=ReviewSeverity.HIGH,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        requirements = evidence.get_by_type("requirement")
        verification = evidence.get_by_type("verification_result")

        if not requirements:
            return self._inconclusive("No requirements evidence available")

        satisfied_count = 0
        unsatisfied = []
        unverified = []
        findings = []

        for req in requirements:
            req_data = req.data.get("requirements", [])
            for r in req_data:
                status = r.get("status", "unknown")
                if status == "satisfied":
                    satisfied_count += 1
                elif status == "unverified":
                    unverified.append(r)
                else:
                    unsatisfied.append(r)
                    findings.append(ReviewFinding(
                        category=FindingCategory.REQUIREMENT,
                        severity=ReviewSeverity.HIGH,
                        summary=f"Requirement not satisfied: {r.get('description', 'unknown')}",
                        detail=r.get("detail", ""),
                        evidence={"requirement": r},
                    ))

        total = len(requirements)
        if total == 0:
            return self._inconclusive("No requirements to evaluate")

        if not unsatisfied and not unverified:
            return self._pass(
                summary=f"All {satisfied_count} requirements satisfied",
                evidence={"satisfied": satisfied_count, "total": total},
            )

        if unsatisfied:
            if satisfied_count > 0:
                return CriterionResult(
                    criterion=self._name,
                    status=CriterionStatus.WARNING,
                    severity=ReviewSeverity.MEDIUM,
                    summary=f"{satisfied_count}/{total} requirements satisfied",
                    findings=findings,
                    evidence={"satisfied": satisfied_count, "total": total},
                )

            return self._fail(
                summary=f"No requirements satisfied ({total} total)",
                findings=findings,
                evidence={"satisfied": 0, "total": total},
            )

        # Only unverified requirements
        return self._inconclusive(
            f"{len(unverified)} requirements unverified",
            evidence={"unverified": len(unverified), "total": total},
        )


class VerificationCriterion(ReviewCriterion):
    """Checks verification results."""

    def __init__(self):
        super().__init__(
            name="verification",
            category=FindingCategory.VERIFICATION,
            severity=ReviewSeverity.HIGH,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        verification = evidence.get_by_type("verification_result")

        if not verification:
            return self._inconclusive("No verification results available")

        latest = verification[-1]
        result_data = latest.data.get("result", {})
        passed = result_data.get("passed", False)
        total = result_data.get("total", 0)
        failures = result_data.get("failures", [])

        if passed:
            return self._pass(
                summary=f"Verification passed ({total} checks)",
                evidence={"passed": True, "total": total},
            )

        findings = []
        for failure in failures:
            findings.append(ReviewFinding(
                category=FindingCategory.VERIFICATION,
                severity=ReviewSeverity.HIGH,
                summary=f"Verification failed: {failure.get('name', 'unknown')}",
                detail=failure.get("message", ""),
                evidence={"failure": failure},
            ))

        return self._fail(
            summary=f"Verification failed ({len(failures)} failures)",
            findings=findings,
            evidence={"passed": False, "failures": len(failures)},
        )


class RegressionCriterion(ReviewCriterion):
    """Checks for regressions."""

    def __init__(self):
        super().__init__(
            name="regression",
            category=FindingCategory.REGRESSION,
            severity=ReviewSeverity.HIGH,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        regression = evidence.get_by_type("regression_result")

        if not regression:
            return self._inconclusive("No regression check results available")

        latest = regression[-1]
        result_data = latest.data.get("result", {})
        has_regression = result_data.get("has_regression", False)
        new_failures = result_data.get("new_failures", [])
        baseline_available = result_data.get("baseline_available", False)

        if not baseline_available:
            return CriterionResult(
                criterion=self._name,
                status=CriterionStatus.INCONCLUSIVE,
                severity=ReviewSeverity.INFO,
                summary="No baseline available for regression comparison",
                evidence={"baseline_available": False},
                confidence=0.3,
            )

        if not has_regression:
            return self._pass(
                summary="No regressions detected",
                evidence={"has_regression": False},
            )

        findings = []
        for failure in new_failures:
            findings.append(ReviewFinding(
                category=FindingCategory.REGRESSION,
                severity=ReviewSeverity.HIGH,
                summary=f"New regression: {failure.get('name', 'unknown')}",
                detail=failure.get("message", ""),
                evidence={"failure": failure},
            ))

        return self._fail(
            summary=f"Regression detected ({len(new_failures)} new failures)",
            findings=findings,
            evidence={"has_regression": True, "new_failures": len(new_failures)},
        )


class SecurityCriterion(ReviewCriterion):
    """Checks security evidence."""

    def __init__(self):
        super().__init__(
            name="security",
            category=FindingCategory.SECURITY,
            severity=ReviewSeverity.CRITICAL,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        security_events = evidence.get_by_type("security_event")
        audit_events = evidence.get_by_type("audit_event")

        findings = []

        # Check for security denials
        for event in security_events:
            event_data = event.data.get("event", {})
            if event_data.get("decision") == "deny":
                findings.append(ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    summary=f"Security denied: {event_data.get('capability', 'unknown')}",
                    detail=event_data.get("reason", ""),
                    evidence={"event": event_data},
                ))

        # Check for injection detection
        for event in security_events:
            event_data = event.data.get("event", {})
            if event_data.get("type") == "injection_detected":
                findings.append(ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    summary="Prompt injection detected",
                    detail=event_data.get("injection_type", ""),
                    evidence={"event": event_data},
                ))

        # Check audit trail for violations
        for event in audit_events:
            event_data = event.data.get("event", {})
            if event_data.get("event_type") in ("policy_violation", "injection_detected"):
                findings.append(ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.HIGH,
                    summary=f"Audit violation: {event_data.get('event_type', 'unknown')}",
                    detail=event_data.get("reason", ""),
                    evidence={"event": event_data},
                ))

        if findings:
            return self._fail(
                summary=f"Security findings detected ({len(findings)} issues)",
                findings=findings,
                evidence={"findings_count": len(findings)},
            )

        return self._pass(
            summary="No security findings",
            evidence={"security_events_checked": len(security_events)},
        )


class DiffQualityCriterion(ReviewCriterion):
    """Checks diff quality."""

    def __init__(self):
        super().__init__(
            name="diff_quality",
            category=FindingCategory.DIFF,
            severity=ReviewSeverity.MEDIUM,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        diff_evidence = evidence.get_by_type("git_diff")

        if not diff_evidence:
            return self._inconclusive("No diff evidence available")

        latest = diff_evidence[-1]
        diff_data = latest.data.get("diff", {})
        files_changed = diff_data.get("files_changed", [])
        lines_added = diff_data.get("lines_added", 0)
        lines_removed = diff_data.get("lines_removed", 0)

        findings = []

        # Check for debug prints
        if diff_data.get("has_debug_prints", False):
            findings.append(ReviewFinding(
                category=FindingCategory.QUALITY,
                severity=ReviewSeverity.LOW,
                summary="Debug print statements detected",
                detail="Consider removing debug prints before merge",
                evidence={"files": diff_data.get("debug_print_files", [])},
            ))

        # Check for hardcoded secrets
        if diff_data.get("has_hardcoded_secrets", False):
            findings.append(ReviewFinding(
                category=FindingCategory.SECURITY,
                severity=ReviewSeverity.CRITICAL,
                summary="Potential hardcoded secrets detected",
                detail="Secrets should not be hardcoded in source code",
                evidence={"files": diff_data.get("secret_files", [])},
            ))

        # Check for large diffs
        total_lines = lines_added + lines_removed
        if total_lines > 500:
            findings.append(ReviewFinding(
                category=FindingCategory.QUALITY,
                severity=ReviewSeverity.LOW,
                summary=f"Large diff: {total_lines} lines changed",
                detail="Consider breaking into smaller changes",
                evidence={"lines_added": lines_added, "lines_removed": lines_removed},
            ))

        # Check for test deletion
        if diff_data.get("tests_deleted", 0) > 0:
            findings.append(ReviewFinding(
                category=FindingCategory.TEST_DELETION,
                severity=ReviewSeverity.HIGH,
                summary=f"Tests deleted: {diff_data.get('tests_deleted', 0)}",
                detail="Test deletion may indicate hidden regressions",
                evidence={"deleted_tests": diff_data.get("deleted_tests", [])},
            ))

        if findings:
            # Check if any critical findings
            if any(f.severity == ReviewSeverity.CRITICAL for f in findings):
                return self._fail(
                    summary=f"Diff quality findings ({len(findings)} issues)",
                    findings=findings,
                    evidence={"files_changed": len(files_changed)},
                )
            return CriterionResult(
                criterion=self._name,
                status=CriterionStatus.WARNING if all(
                    f.severity <= ReviewSeverity.MEDIUM for f in findings
                ) else CriterionStatus.FAIL,
                severity=max((f.severity for f in findings), default=ReviewSeverity.INFO),
                summary=f"Diff quality findings ({len(findings)} issues)",
                findings=findings,
                evidence={"files_changed": len(files_changed)},
            )

        return self._pass(
            summary=f"Diff quality acceptable ({len(files_changed)} files changed)",
            evidence={"files_changed": len(files_changed), "total_lines": total_lines},
        )


class ScopeCriterion(ReviewCriterion):
    """Checks if changes stay within task scope."""

    def __init__(self):
        super().__init__(
            name="scope",
            category=FindingCategory.SCOPE,
            severity=ReviewSeverity.MEDIUM,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        scope_evidence = evidence.get_by_type("scope_check")

        if not scope_evidence:
            return self._inconclusive("No scope check evidence available")

        latest = scope_evidence[-1]
        scope_data = latest.data.get("scope", {})
        in_scope_files = scope_data.get("in_scope_files", [])
        out_of_scope_files = scope_data.get("out_of_scope_files", [])

        if not out_of_scope_files:
            return self._pass(
                summary="All changes within scope",
                evidence={"in_scope": len(in_scope_files), "out_of_scope": 0},
            )

        findings = []
        for f in out_of_scope_files:
            findings.append(ReviewFinding(
                category=FindingCategory.SCOPE,
                severity=ReviewSeverity.MEDIUM,
                summary=f"Out-of-scope file changed: {f.get('file', 'unknown')}",
                detail=f.get("reason", "File not related to task requirements"),
                evidence={"file": f},
            ))

        return CriterionResult(
            criterion=self._name,
            status=CriterionStatus.WARNING,
            severity=ReviewSeverity.MEDIUM,
            summary=f"{len(out_of_scope_files)} out-of_scope file changes detected",
            findings=findings,
            evidence={"in_scope": len(in_scope_files), "out_of_scope": len(out_of_scope_files)},
        )


class TestDeletionCriterion(ReviewCriterion):
    """Checks for suspicious test deletions."""

    def __init__(self):
        super().__init__(
            name="test_deletion",
            category=FindingCategory.TEST_DELETION,
            severity=ReviewSeverity.HIGH,
        )

    def evaluate(self, evidence: EvidenceCollection) -> CriterionResult:
        test_evidence = evidence.get_by_type("test_result")
        diff_evidence = evidence.get_by_type("git_diff")

        findings = []

        # Check diff for test deletions
        for diff in diff_evidence:
            diff_data = diff.data.get("diff", {})
            deleted_tests = diff_data.get("deleted_tests", [])
            for test in deleted_tests:
                findings.append(ReviewFinding(
                    category=FindingCategory.TEST_DELETION,
                    severity=ReviewSeverity.HIGH,
                    summary=f"Test deleted: {test.get('name', 'unknown')}",
                    detail="Test deletion may hide regressions",
                    evidence={"test": test},
                ))

        # Check for weakened assertions
        for diff in diff_evidence:
            diff_data = diff.data.get("diff", {})
            weakened = diff_data.get("weakened_assertions", [])
            for w in weakened:
                findings.append(ReviewFinding(
                    category=FindingCategory.TEST_DELETION,
                    severity=ReviewSeverity.MEDIUM,
                    summary=f"Weakened assertion: {w.get('test', 'unknown')}",
                    detail=w.get("detail", ""),
                    evidence={"weakened": w},
                ))

        if findings:
            return self._fail(
                summary=f"Test deletion/weakening detected ({len(findings)} issues)",
                findings=findings,
                evidence={"findings_count": len(findings)},
            )

        return self._pass(
            summary="No suspicious test deletions",
            evidence={"tests_checked": len(test_evidence)},
        )
