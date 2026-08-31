"""Evidence collection for ARGUS review."""

from typing import Any, Dict, List, Optional

from argus.review.models import EvidenceCollection, ReviewEvidence


class EvidenceCollector:
    """Collects and manages evidence for review."""

    def __init__(self):
        self._collection = EvidenceCollection()

    @property
    def collection(self) -> EvidenceCollection:
        return self._collection

    def add_evidence(
        self,
        source: str,
        evidence_type: str,
        data: Dict[str, Any],
        reliability: float = 1.0,
        summary: str = "",
        run_id: str = "",
    ) -> ReviewEvidence:
        """Add evidence to the collection."""
        evidence = ReviewEvidence(
            source=source,
            evidence_type=evidence_type,
            data=data,
            reliability=reliability,
            summary=summary,
            run_id=run_id,
        )
        self._collection.add(evidence)
        return evidence

    def add_requirements(self, requirements: List[Dict[str, Any]], run_id: str = "") -> ReviewEvidence:
        """Add requirement evidence."""
        return self.add_evidence(
            source="task",
            evidence_type="requirement",
            data={"requirements": requirements},
            summary=f"{len(requirements)} requirements",
            run_id=run_id,
        )

    def add_verification_result(self, passed: bool, total: int, failures: List[Dict] = None,
                                run_id: str = "") -> ReviewEvidence:
        """Add verification result evidence."""
        return self.add_evidence(
            source="verification_engine",
            evidence_type="verification_result",
            data={
                "result": {
                    "passed": passed,
                    "total": total,
                    "failures": failures or [],
                }
            },
            summary=f"Verification {'passed' if passed else 'failed'} ({total} checks)",
            run_id=run_id,
        )

    def add_regression_result(self, has_regression: bool, new_failures: List[Dict] = None,
                              baseline_available: bool = True, run_id: str = "") -> ReviewEvidence:
        """Add regression check evidence."""
        return self.add_evidence(
            source="regression_checker",
            evidence_type="regression_result",
            data={
                "result": {
                    "has_regression": has_regression,
                    "new_failures": new_failures or [],
                    "baseline_available": baseline_available,
                }
            },
            summary=f"Regression {'detected' if has_regression else 'not detected'}",
            run_id=run_id,
        )

    def add_security_event(self, event: Dict[str, Any], run_id: str = "") -> ReviewEvidence:
        """Add security event evidence."""
        return self.add_evidence(
            source="security_kernel",
            evidence_type="security_event",
            data={"event": event},
            summary=f"Security event: {event.get('type', 'unknown')}",
            run_id=run_id,
        )

    def add_audit_event(self, event: Dict[str, Any], run_id: str = "") -> ReviewEvidence:
        """Add audit event evidence."""
        return self.add_evidence(
            source="audit_trail",
            evidence_type="audit_event",
            data={"event": event},
            summary=f"Audit event: {event.get('event_type', 'unknown')}",
            run_id=run_id,
        )

    def add_git_diff(self, diff_data: Dict[str, Any], run_id: str = "") -> ReviewEvidence:
        """Add git diff evidence."""
        return self.add_evidence(
            source="git",
            evidence_type="git_diff",
            data={"diff": diff_data},
            summary=f"Diff: {diff_data.get('files_changed', [])} files changed",
            run_id=run_id,
        )

    def add_scope_check(self, in_scope: List[Dict], out_of_scope: List[Dict],
                        run_id: str = "") -> ReviewEvidence:
        """Add scope check evidence."""
        return self.add_evidence(
            source="scope_checker",
            evidence_type="scope_check",
            data={"scope": {"in_scope_files": in_scope, "out_of_scope_files": out_of_scope}},
            summary=f"Scope: {len(in_scope)} in-scope, {len(out_of_scope)} out-of-scope",
            run_id=run_id,
        )

    def add_test_result(self, results: Dict[str, Any], run_id: str = "") -> ReviewEvidence:
        """Add test result evidence."""
        return self.add_evidence(
            source="test_runner",
            evidence_type="test_result",
            data={"results": results},
            summary=f"Tests: {results.get('passed', 0)} passed, {results.get('failed', 0)} failed",
            run_id=run_id,
        )

    def add_mcp_activity(self, activity: Dict[str, Any], run_id: str = "") -> ReviewEvidence:
        """Add MCP activity evidence."""
        return self.add_evidence(
            source="mcp_client",
            evidence_type="mcp_activity",
            data={"activity": activity},
            summary=f"MCP: {activity.get('server_id', 'unknown')} - {activity.get('action', 'unknown')}",
            run_id=run_id,
        )

    def add_recovery_history(self, history: List[Dict[str, Any]], run_id: str = "") -> ReviewEvidence:
        """Add recovery history evidence."""
        return self.add_evidence(
            source="recovery_engine",
            evidence_type="recovery_history",
            data={"history": history},
            summary=f"Recovery: {len(history)} attempts",
            run_id=run_id,
        )

    def has_evidence_type(self, evidence_type: str) -> bool:
        """Check if evidence of a type exists."""
        return self._collection.has_type(evidence_type)

    def get_evidence_type(self, evidence_type: str) -> List[ReviewEvidence]:
        """Get all evidence of a type."""
        return self._collection.get_by_type(evidence_type)

    def clear(self) -> None:
        """Clear all evidence."""
        self._collection.evidence.clear()

    def summary(self) -> Dict[str, Any]:
        """Get evidence summary."""
        return {
            "total_evidence": len(self._collection.evidence),
            "types": self._collection.types,
            "sources": self._collection.sources,
        }
