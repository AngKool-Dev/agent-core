"""Review analyzer for ARGUS."""

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


class DiffAnalyzer:
    """Analyzes git diffs for review."""

    SUSPICIOUS_PATTERNS = [
        (r"print\s*\(", "debug print"),
        (r"console\.log\s*\(", "console.log debug"),
        (r"debugger", "debugger statement"),
        (r"TODO[: ]", "TODO comment"),
        (r"FIXME[: ]", "FIXME comment"),
        (r"HACK[: ]", "HACK comment"),
        (r"XXX[: ]", "XXX comment"),
    ]

    SECRET_PATTERNS = [
        (r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})", "API key"),
        (r"(?:secret[_-]?key|secretkey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})", "secret key"),
        (r"(?:password|passwd)\s*[:=]\s*['\"]?([^\s'\"]{8,})", "password"),
        (r"(?:bearer)\s+([a-zA-Z0-9_\-\.]{16,})", "bearer token"),
        (r"gh[pousr]_[A-Za-z0-9_]{36,}", "GitHub token"),
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI key"),
    ]

    def analyze(self, diff_data: Dict[str, Any]) -> List[ReviewFinding]:
        """Analyze a diff for quality issues."""
        findings = []

        # Check for debug prints
        debug_files = self._find_debug_prints(diff_data)
        for f in debug_files:
            findings.append(ReviewFinding(
                category=FindingCategory.QUALITY,
                severity=ReviewSeverity.LOW,
                summary=f"Debug print detected in {f}",
                detail="Consider removing debug prints before merge",
                file=f,
            ))

        # Check for hardcoded secrets
        secret_files = self._find_secrets(diff_data)
        for f, secret_type in secret_files:
            findings.append(ReviewFinding(
                category=FindingCategory.SECURITY,
                severity=ReviewSeverity.CRITICAL,
                summary=f"Potential hardcoded {secret_type} in {f}",
                detail="Secrets should not be hardcoded in source code",
                file=f,
                recommendation="Use environment variables or a secrets manager",
            ))

        # Check for test deletion
        deleted_tests = diff_data.get("deleted_tests", [])
        for test in deleted_tests:
            findings.append(ReviewFinding(
                category=FindingCategory.TEST_DELETION,
                severity=ReviewSeverity.HIGH,
                summary=f"Test deleted: {test.get('name', 'unknown')}",
                detail="Test deletion may indicate hidden regressions",
                file=test.get("file"),
            ))

        # Check for weakened assertions
        weakened = diff_data.get("weakened_assertions", [])
        for w in weakened:
            findings.append(ReviewFinding(
                category=FindingCategory.TEST_DELETION,
                severity=ReviewSeverity.MEDIUM,
                summary=f"Weakened assertion in {w.get('test', 'unknown')}",
                detail=w.get("detail", ""),
                file=w.get("file"),
            ))

        return findings

    def _find_debug_prints(self, diff_data: Dict[str, Any]) -> List[str]:
        """Find files with debug prints."""
        return diff_data.get("debug_print_files", [])

    def _find_secrets(self, diff_data: Dict[str, Any]) -> List[tuple]:
        """Find files with potential secrets."""
        return diff_data.get("secret_files", [])

    def analyze_scope(self, task_files: List[str], changed_files: List[str]) -> Dict[str, Any]:
        """Analyze if changes are within scope."""
        in_scope = []
        out_of_scope = []

        for f in changed_files:
            if any(tf in f or f in tf for tf in task_files):
                in_scope.append({"file": f, "reason": "Matches task requirement"})
            else:
                out_of_scope.append({"file": f, "reason": "No matching requirement"})

        return {"in_scope_files": in_scope, "out_of_scope_files": out_of_scope}


class RequirementAnalyzer:
    """Analyzes requirement satisfaction."""

    def analyze(self, requirements: List[Dict[str, Any]],
                evidence: Dict[str, Any]) -> List[ReviewFinding]:
        """Analyze requirement satisfaction."""
        findings = []

        for req in requirements:
            status = req.get("status", "unknown")
            description = req.get("description", "unknown requirement")

            if status == "unsatisfied":
                findings.append(ReviewFinding(
                    category=FindingCategory.REQUIREMENT,
                    severity=ReviewSeverity.HIGH,
                    summary=f"Requirement not satisfied: {description}",
                    detail=req.get("detail", ""),
                    evidence={"requirement": req},
                ))
            elif status == "partially_satisfied":
                findings.append(ReviewFinding(
                    category=FindingCategory.REQUIREMENT,
                    severity=ReviewSeverity.MEDIUM,
                    summary=f"Requirement partially satisfied: {description}",
                    detail=req.get("detail", ""),
                    evidence={"requirement": req},
                ))
            elif status == "unverified":
                findings.append(ReviewFinding(
                    category=FindingCategory.REQUIREMENT,
                    severity=ReviewSeverity.MEDIUM,
                    summary=f"Requirement unverified: {description}",
                    detail="No evidence available to verify this requirement",
                    evidence={"requirement": req},
                ))

        return findings


class SecurityAnalyzer:
    """Analyzes security evidence."""

    def analyze(self, security_events: List[Dict[str, Any]],
                audit_events: List[Dict[str, Any]]) -> List[ReviewFinding]:
        """Analyze security evidence."""
        findings = []

        for event in security_events:
            if event.get("decision") == "deny":
                findings.append(ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    summary=f"Security denied: {event.get('capability', 'unknown')}",
                    detail=event.get("reason", ""),
                    evidence={"event": event},
                ))

            if event.get("type") == "injection_detected":
                findings.append(ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.CRITICAL,
                    summary="Prompt injection detected",
                    detail=event.get("injection_type", ""),
                    evidence={"event": event},
                ))

        for event in audit_events:
            if event.get("event_type") in ("policy_violation", "injection_detected"):
                findings.append(ReviewFinding(
                    category=FindingCategory.SECURITY,
                    severity=ReviewSeverity.HIGH,
                    summary=f"Audit violation: {event.get('event_type', 'unknown')}",
                    detail=event.get("reason", ""),
                    evidence={"event": event},
                ))

        return findings


class RegressionAnalyzer:
    """Analyzes regression evidence."""

    def analyze(self, regression_result: Dict[str, Any]) -> List[ReviewFinding]:
        """Analyze regression check results."""
        findings = []

        has_regression = regression_result.get("has_regression", False)
        new_failures = regression_result.get("new_failures", [])
        baseline_available = regression_result.get("baseline_available", False)

        if not baseline_available:
            findings.append(ReviewFinding(
                category=FindingCategory.REGRESSION,
                severity=ReviewSeverity.LOW,
                summary="No baseline available for regression comparison",
                detail="Cannot definitively determine regression status",
                evidence={"baseline_available": False},
            ))
            return findings

        if has_regression:
            for failure in new_failures:
                findings.append(ReviewFinding(
                    category=FindingCategory.REGRESSION,
                    severity=ReviewSeverity.HIGH,
                    summary=f"New regression: {failure.get('name', 'unknown')}",
                    detail=failure.get("message", ""),
                    evidence={"failure": failure},
                ))

        return findings
