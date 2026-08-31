"""Subagent result handling for ARGUS."""

from typing import Any, Dict, List, Optional

from argus.subagents.models import SubagentResult, SubagentStatus


class ResultFormatter:
    """Formats subagent results for different outputs."""

    @staticmethod
    def to_text(result: SubagentResult) -> str:
        """Format result as human-readable text."""
        lines = [
            f"Subagent Result: {result.subagent_id}",
            f"Status: {result.status.value}",
            f"Summary: {result.summary}",
        ]

        if result.findings:
            lines.append("")
            lines.append("Findings:")
            for i, finding in enumerate(result.findings, 1):
                lines.append(f"  {i}. {finding.get('summary', 'No summary')}")

        if result.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in result.errors:
                lines.append(f"  - {error}")

        if result.budget_usage:
            lines.append("")
            lines.append("Budget Usage:")
            for key, value in result.budget_usage.items():
                lines.append(f"  {key}: {value}")

        if result.duration:
            lines.append(f"Duration: {result.duration:.2f}s")

        return "\n".join(lines)

    @staticmethod
    def to_dict(result: SubagentResult) -> Dict[str, Any]:
        """Format result as dictionary."""
        return result.to_dict()

    @staticmethod
    def to_json(result: SubagentResult) -> str:
        """Format result as JSON."""
        import json
        return json.dumps(result.to_dict(), indent=2, default=str)


def summarize_results(results: List[SubagentResult]) -> Dict[str, Any]:
    """Summarize multiple results."""
    if not results:
        return {"count": 0, "status": "no_results"}

    status_counts: Dict[str, int] = {}
    for result in results:
        status = result.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    total_findings = sum(len(r.findings) for r in results)
    total_errors = sum(len(r.errors) for r in results)
    total_recommendations = sum(len(r.recommendations) for r in results)

    return {
        "count": len(results),
        "status_counts": status_counts,
        "total_findings": total_findings,
        "total_errors": total_errors,
        "total_recommendations": total_recommendations,
        "success_rate": sum(1 for r in results if r.status == SubagentStatus.COMPLETED) / len(results),
    }
