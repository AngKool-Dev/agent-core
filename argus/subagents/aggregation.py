"""Result aggregation for ARGUS subagents."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.subagents.models import SubagentResult, SubagentStatus


@dataclass
class AggregationResult:
    """Result of aggregating multiple subagent results."""
    status: str = "unknown"
    summary: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    subagent_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": self.findings,
            "conflicts": self.conflicts,
            "evidence": self.evidence,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "subagent_count": self.subagent_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }


class ResultAggregator:
    """Aggregates results from multiple subagents."""

    def aggregate(self, results: List[SubagentResult]) -> AggregationResult:
        """Aggregate multiple subagent results."""
        if not results:
            return AggregationResult(
                status="no_results",
                summary="No results to aggregate",
            )

        # Count successes and failures
        success_count = sum(1 for r in results if r.status == SubagentStatus.COMPLETED)
        failure_count = sum(1 for r in results if r.status in (
            SubagentStatus.FAILED,
            SubagentStatus.TIMED_OUT,
            SubagentStatus.BLOCKED,
        ))

        # Collect all findings
        all_findings = []
        for result in results:
            all_findings.extend(result.findings)

        # Collect all evidence
        all_evidence = []
        for result in results:
            all_evidence.extend(result.evidence)

        # Collect all recommendations
        all_recommendations = []
        for result in results:
            all_recommendations.extend(result.recommendations)

        # Detect conflicts
        conflicts = self._detect_conflicts(results)

        # Determine overall status
        status = self._determine_status(results, conflicts)

        # Calculate confidence
        confidence = self._calculate_confidence(results, conflicts)

        # Generate summary
        summary = self._generate_summary(results, status, conflicts)

        return AggregationResult(
            status=status,
            summary=summary,
            findings=all_findings,
            conflicts=conflicts,
            evidence=all_evidence,
            recommendations=all_recommendations,
            confidence=confidence,
            subagent_count=len(results),
            success_count=success_count,
            failure_count=failure_count,
        )

    def _detect_conflicts(self, results: List[SubagentResult]) -> List[Dict[str, Any]]:
        """Detect conflicts between subagent results."""
        conflicts = []

        # Group findings by topic
        findings_by_topic: Dict[str, List[Dict[str, Any]]] = {}
        for result in results:
            for finding in result.findings:
                topic = finding.get("topic", "unknown")
                if topic not in findings_by_topic:
                    findings_by_topic[topic] = []
                findings_by_topic[topic].append({
                    "subagent_id": result.subagent_id,
                    "finding": finding,
                })

        # Check for conflicting conclusions on the same topic
        for topic, findings in findings_by_topic.items():
            if len(findings) < 2:
                continue

            # Check for conflicting conclusions
            conclusions = set()
            for f in findings:
                conclusion = f["finding"].get("conclusion", "")
                if conclusion:
                    conclusions.add(conclusion)

            if len(conclusions) > 1:
                conflicts.append({
                    "topic": topic,
                    "type": "conflicting_conclusions",
                    "findings": findings,
                })

        return conflicts

    def _determine_status(
        self,
        results: List[SubagentResult],
        conflicts: List[Dict[str, Any]],
    ) -> str:
        """Determine overall status."""
        # If any critical failures, status is failed
        if any(r.status == SubagentStatus.FAILED for r in results):
            return "failed"

        # If any blocked, status is blocked
        if any(r.status == SubagentStatus.BLOCKED for r in results):
            return "blocked"

        # If conflicts exist, status is conflicting
        if conflicts:
            return "conflicting"

        # If all completed, status is success
        if all(r.status == SubagentStatus.COMPLETED for r in results):
            return "success"

        # If any timed out, status is partial
        if any(r.status == SubagentStatus.TIMED_OUT for r in results):
            return "partial"

        return "unknown"

    def _calculate_confidence(
        self,
        results: List[SubagentResult],
        conflicts: List[Dict[str, Any]],
    ) -> float:
        """Calculate confidence in the aggregated result."""
        if not results:
            return 0.0

        # Base confidence on success rate
        success_count = sum(1 for r in results if r.status == SubagentStatus.COMPLETED)
        base_confidence = success_count / len(results)

        # Reduce confidence if conflicts exist
        if conflicts:
            base_confidence *= 0.7

        return round(base_confidence, 2)

    def _generate_summary(
        self,
        results: List[SubagentResult],
        status: str,
        conflicts: List[Dict[str, Any]],
    ) -> str:
        """Generate a summary of the aggregation."""
        parts = [f"Aggregated {len(results)} subagent results"]
        parts.append(f"Status: {status}")

        success_count = sum(1 for r in results if r.status == SubagentStatus.COMPLETED)
        parts.append(f"Success: {success_count}/{len(results)}")

        if conflicts:
            parts.append(f"Conflicts: {len(conflicts)}")

        return ", ".join(parts)
