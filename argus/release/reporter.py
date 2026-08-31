"""Release qualification reporter for ARGUS."""

from typing import Any, Dict

from argus.release.models import ArtifactStatus, InvariantStatus, ReleaseRun


class ReleaseReporter:
    """Generates release qualification reports."""

    def generate_text_report(self, run: ReleaseRun) -> str:
        """Generate a text-based release report."""
        lines = []

        lines.append("=" * 70)
        lines.append("ARGUS 1.0.0 RELEASE QUALIFICATION REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Version
        lines.append("VERSION")
        lines.append("-" * 40)
        if run.version_info:
            lines.append(f"Package: {run.version_info.package_version}")
            lines.append(f"CLI: {run.version_info.cli_version}")
            lines.append(f"Metadata: {run.version_info.metadata_version}")
            lines.append(f"Consistent: {run.version_info.is_consistent}")
        lines.append("")

        # Artifact Results
        lines.append("ARTIFACT VALIDATION")
        lines.append("-" * 40)
        for name, result in run.artifact_results.items():
            status = result.status.value.upper()
            lines.append(f"  [{status}] {name}: {result.artifact_path}")
            if result.errors:
                for error in result.errors:
                    lines.append(f"    ERROR: {error}")
            if result.warnings:
                for warning in result.warnings:
                    lines.append(f"    WARNING: {warning}")
        lines.append("")

        # Invariant Results
        lines.append("RELEASE INVARIANTS")
        lines.append("-" * 40)
        for name, result in run.invariant_results.items():
            status = result.status.value.upper()
            lines.append(f"  [{status}] {name}: {result.description}")
            if result.evidence:
                lines.append(f"    Evidence: {result.evidence}")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Checks: {run.total_checks}")
        lines.append(f"Passed: {run.passed}")
        lines.append(f"Failed: {run.failed}")
        lines.append(f"Skipped: {run.skipped}")
        lines.append(f"Inconclusive: {run.inconclusive}")
        lines.append(f"Pass Rate: {run.pass_rate:.1%}")
        lines.append(f"Duration: {run.total_duration:.2f}s")
        lines.append("")

        # Release Decision
        decision = self._make_release_decision(run)
        lines.append("RELEASE DECISION")
        lines.append("-" * 40)
        lines.append(f"Decision: {decision}")
        lines.append("")

        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json_report(self, run: ReleaseRun) -> Dict[str, Any]:
        """Generate a JSON release report."""
        return {
            "report_type": "release_qualification",
            "version": "1.0.0",
            "run_id": run.run_id,
            "run_data": run.to_dict(),
            "release_decision": self._make_release_decision(run),
        }

    def _make_release_decision(self, run: ReleaseRun) -> str:
        """Make a release decision based on results."""
        # Check for blocking failures
        for result in run.invariant_results.values():
            if result.status == InvariantStatus.FAIL:
                return "BLOCKED"

        for result in run.artifact_results.values():
            if result.status == ArtifactStatus.INVALID:
                return "BLOCKED"

        # Check pass rate
        if run.total_checks > 0:
            pass_rate = run.passed / run.total_checks
            if pass_rate >= 0.9:
                return "QUALIFIED"
            elif pass_rate >= 0.7:
                return "QUALIFIED_WITH_LIMITATIONS"

        return "QUALIFIED_WITH_LIMITATIONS"


def generate_release_report(run: ReleaseRun, format: str = "text") -> str:
    """Convenience function to generate a release report."""
    reporter = ReleaseReporter()
    if format == "json":
        import json
        return json.dumps(reporter.generate_json_report(run), indent=2)
    return reporter.generate_text_report(run)
