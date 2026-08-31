"""Review report generation for ARGUS."""

import json
from typing import Any, Dict, List, Optional

from argus.review.models import (
    CriterionResult,
    CriterionStatus,
    FindingCategory,
    ReviewFinding,
    ReviewResult,
    ReviewStatus,
    ReviewSeverity,
)


class ReviewReport:
    """Generates human-readable and machine-readable review reports."""

    SEVERITY_ICONS = {
        ReviewSeverity.INFO: "ℹ",
        ReviewSeverity.LOW: "•",
        ReviewSeverity.MEDIUM: "⚠",
        ReviewSeverity.HIGH: "✗",
        ReviewSeverity.CRITICAL: "✗",
    }

    STATUS_ICONS = {
        ReviewStatus.PASS: "✓",
        ReviewStatus.PASS_WITH_WARNINGS: "✓",
        ReviewStatus.FAIL: "✗",
        ReviewStatus.BLOCKED: "✗",
        ReviewStatus.INCONCLUSIVE: "?",
    }

    def __init__(self, result: ReviewResult):
        self._result = result

    @property
    def result(self) -> ReviewResult:
        return self._result

    def to_text(self) -> str:
        """Generate human-readable text report."""
        lines = [
            "ARGUS REVIEW",
            "─" * 60,
            "",
        ]

        # Summary
        status_icon = self.STATUS_ICONS.get(self._result.status, "?")
        lines.append(f"Result: {status_icon} {self._result.status.value.upper()}")
        lines.append(f"Summary: {self._result.summary}")

        if self._result.task:
            lines.append(f"Task: {self._result.task}")

        lines.append("")

        # Criteria results
        if self._result.criteria:
            lines.append("Criteria:")
            for criterion in self._result.criteria:
                icon = self._criterion_icon(criterion.status)
                lines.append(f"  {icon} {criterion.criterion}: {criterion.status.value}")
                if criterion.summary:
                    lines.append(f"    {criterion.summary}")

            lines.append("")

        # Findings
        if self._result.findings:
            lines.append("Findings:")
            for finding in sorted(self._result.findings, key=lambda f: f.severity.value, reverse=True):
                icon = self.SEVERITY_ICONS.get(finding.severity, "?")
                lines.append(f"  {icon} [{finding.severity.value.upper()}] {finding.summary}")
                if finding.detail:
                    lines.append(f"    {finding.detail}")
                if finding.recommendation:
                    lines.append(f"    Recommendation: {finding.recommendation}")
                if finding.file:
                    lines.append(f"    File: {finding.file}")

            lines.append("")

        # Statistics
        stats = self._compute_statistics()
        lines.append("Statistics:")
        lines.append(f"  Total criteria: {stats['total_criteria']}")
        lines.append(f"  Passed: {stats['passed']}")
        lines.append(f"  Failed: {stats['failed']}")
        lines.append(f"  Warnings: {stats['warnings']}")
        lines.append(f"  Inconclusive: {stats['inconclusive']}")
        lines.append(f"  Total findings: {stats['total_findings']}")

        if stats['critical_findings'] > 0:
            lines.append(f"  Critical findings: {stats['critical_findings']}")
        if stats['high_findings'] > 0:
            lines.append(f"  High-severity findings: {stats['high_findings']}")

        if self._result.duration:
            lines.append(f"  Duration: {self._result.duration:.3f}s")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Generate JSON report."""
        return self._result.to_json()

    def to_dict(self) -> Dict[str, Any]:
        """Generate dict report."""
        return self._result.to_dict()

    def _criterion_icon(self, status: CriterionStatus) -> str:
        """Get icon for criterion status."""
        icons = {
            CriterionStatus.PASS: "✓",
            CriterionStatus.FAIL: "✗",
            CriterionStatus.WARNING: "⚠",
            CriterionStatus.INCONCLUSIVE: "?",
            CriterionStatus.SKIPPED: "•",
        }
        return icons.get(status, "?")

    def _compute_statistics(self) -> Dict[str, Any]:
        """Compute review statistics."""
        return {
            "total_criteria": len(self._result.criteria),
            "passed": sum(1 for c in self._result.criteria if c.status == CriterionStatus.PASS),
            "failed": sum(1 for c in self._result.criteria if c.status == CriterionStatus.FAIL),
            "warnings": sum(1 for c in self._result.criteria if c.status == CriterionStatus.WARNING),
            "inconclusive": sum(1 for c in self._result.criteria if c.status == CriterionStatus.INCONCLUSIVE),
            "total_findings": len(self._result.findings),
            "critical_findings": sum(1 for f in self._result.findings if f.severity == ReviewSeverity.CRITICAL),
            "high_findings": sum(1 for f in self._result.findings if f.severity == ReviewSeverity.HIGH),
        }


def format_review_result(result: ReviewResult) -> str:
    """Format a review result as text."""
    report = ReviewReport(result)
    return report.to_text()


def format_review_json(result: ReviewResult) -> str:
    """Format a review result as JSON."""
    report = ReviewReport(result)
    return report.to_json()
