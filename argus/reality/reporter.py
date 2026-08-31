"""Reality validation reporter for ARGUS qualification."""

from typing import Any, Dict, Optional

from argus.reality.evaluator import RealityEvaluator
from argus.reality.models import (
    RealityRun,
    ReleaseDecision,
    RealityStatus,
)


class RealityReporter:
    """Generates reality validation reports."""

    def __init__(self, evaluator: Optional[RealityEvaluator] = None):
        self._evaluator = evaluator or RealityEvaluator()

    def generate_text_report(self, run: RealityRun) -> str:
        """Generate a text-based reality report."""
        evaluation = self._evaluator.evaluate(run)
        summary = evaluation["summary"]
        lines = []

        lines.append("=" * 70)
        lines.append("ARGUS 1.0.0 PRODUCTION REALITY QUALIFICATION REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Environment
        if run.environment:
            lines.append("ENVIRONMENT")
            lines.append("-" * 40)
            lines.append(f"Python: {run.environment.python_version}")
            lines.append(f"OS: {run.environment.os_name} {run.environment.os_version}")
            lines.append(f"Architecture: {run.environment.architecture}")
            lines.append(f"ARGUS Version: {run.environment.argus_version}")
            lines.append(f"Git Revision: {run.environment.git_revision}")
            lines.append(f"Installation: {run.environment.package_installation_mode}")
            lines.append("")

        # Summary
        lines.append("TEST SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Checks: {summary['total_checks']}")
        lines.append(f"Passed: {summary['passed']}")
        lines.append(f"Failed: {summary['failed']}")
        lines.append(f"Skipped: {summary['skipped']}")
        lines.append(f"Inconclusive: {summary['inconclusive']}")
        lines.append(f"Infrastructure Failures: {summary['infrastructure_failures']}")
        lines.append(f"Pass Rate: {summary['pass_rate']:.1%}")
        lines.append(f"Total Duration: {summary['total_duration']:.2f}s")
        lines.append("")

        # Providers
        providers = evaluation["providers"]
        lines.append("PROVIDERS")
        lines.append("-" * 40)
        if providers["status"] == "tested":
            lines.append(f"Total: {providers['total']}")
            lines.append(f"Available: {providers['available']}")
            for name, info in providers["providers"].items():
                lines.append(f"  {name}: {info['availability']}")
        else:
            lines.append("Not tested")
        lines.append("")

        # MCP
        mcp = evaluation["mcp"]
        lines.append("MCP")
        lines.append("-" * 40)
        if mcp["status"] == "tested":
            lines.append(f"Total: {mcp['total']}")
            lines.append(f"Passed: {mcp['passed']}")
        else:
            lines.append("Not tested")
        lines.append("")

        # Subprocess
        subprocess_eval = evaluation["subprocess"]
        lines.append("SUBPROCESS")
        lines.append("-" * 40)
        if subprocess_eval["status"] == "tested":
            lines.append(f"Total: {subprocess_eval['total']}")
            lines.append(f"Passed: {subprocess_eval['passed']}")
        else:
            lines.append("Not tested")
        lines.append("")

        # Windows
        windows = evaluation["windows"]
        lines.append("WINDOWS")
        lines.append("-" * 40)
        if windows["status"] == "tested":
            lines.append(f"Total: {windows['total']}")
            lines.append(f"Passed: {windows['passed']}")
        else:
            lines.append("Not tested")
        lines.append("")

        # Secrets
        secrets = evaluation["secrets"]
        lines.append("SECRET SAFETY")
        lines.append("-" * 40)
        if secrets["status"] == "tested":
            lines.append(f"Total: {secrets['total']}")
            canary_status = "DETECTED" if secrets["canary_found_anywhere"] else "SAFE"
            lines.append(f"Canary Status: {canary_status}")
        else:
            lines.append("Not tested")
        lines.append("")

        # Invariants
        invariants = evaluation["invariants"]
        lines.append("INVARIANTS")
        lines.append("-" * 40)
        if invariants["status"] == "tested":
            lines.append(f"Total: {invariants['total']}")
            lines.append(f"Passed: {invariants['passed']}")
            for name, info in invariants["invariants"].items():
                status = "PASS" if info["passed"] else "FAIL"
                lines.append(f"  [{status}] {name}: {info['description']}")
        else:
            lines.append("Not tested")
        lines.append("")

        # Scenarios
        scenarios = evaluation["scenarios"]
        lines.append("SCENARIOS")
        lines.append("-" * 40)
        if scenarios["status"] == "tested":
            lines.append(f"Total: {scenarios['total']}")
            lines.append(f"Passed: {scenarios['passed']}")
            lines.append(f"Infrastructure Failures: {scenarios['infrastructure_failures']}")
        else:
            lines.append("Not tested")
        lines.append("")

        # Recommendations
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 40)
        for rec in evaluation["recommendations"]:
            lines.append(f"  - {rec}")
        lines.append("")

        # Release Decision
        decision = self._make_release_decision(run, evaluation)
        lines.append("RELEASE DECISION")
        lines.append("-" * 40)
        lines.append(f"Decision: {decision.decision}")
        lines.append(f"Version: {decision.version}")
        if decision.evidence:
            lines.append("Evidence:")
            for e in decision.evidence:
                lines.append(f"  - {e}")
        if decision.limitations:
            lines.append("Limitations:")
            for l in decision.limitations:
                lines.append(f"  - {l}")
        if decision.risks:
            lines.append("Risks:")
            for r in decision.risks:
                lines.append(f"  - {r}")
        lines.append("")

        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json_report(self, run: RealityRun) -> Dict[str, Any]:
        """Generate a JSON reality report."""
        evaluation = self._evaluator.evaluate(run)
        decision = self._make_release_decision(run, evaluation)

        return {
            "report_type": "reality_qualification",
            "version": "1.0.0",
            "run_id": run.run_id,
            "environment": run.environment.to_dict() if run.environment else None,
            "evaluation": evaluation,
            "release_decision": decision.to_dict(),
            "run_data": run.to_dict(),
        }

    def _make_release_decision(
        self, run: RealityRun, evaluation: Dict[str, Any]
    ) -> ReleaseDecision:
        """Make a release decision based on results."""
        decision = ReleaseDecision(version="1.0.0")

        # Check for critical failures
        failed_invariants = [
            name for name, r in run.invariant_results.items() if not r.passed
        ]
        canary_found = any(
            r.canary_detected for r in run.secret_canary_results.values()
        )

        if failed_invariants or canary_found:
            decision.decision = "BLOCKED"
            if failed_invariants:
                decision.evidence.append(
                    f"Failed invariants: {', '.join(failed_invariants)}"
                )
            if canary_found:
                decision.evidence.append("Secret canary detected in artifacts")
            return decision

        # Check pass rate
        if run.total_checks > 0:
            pass_rate = run.passed / run.total_checks
            if pass_rate >= 0.9:
                decision.decision = "QUALIFIED"
            elif pass_rate >= 0.7:
                decision.decision = "QUALIFIED_WITH_LIMITATIONS"
                decision.limitations.append(
                    f"Pass rate {pass_rate:.1%} below 90% threshold"
                )
            else:
                decision.decision = "BLOCKED"
                decision.evidence.append(
                    f"Pass rate {pass_rate:.1%} below 70% threshold"
                )

        # Add evidence
        decision.evidence.append(f"Total checks: {run.total_checks}")
        decision.evidence.append(f"Passed: {run.passed}")
        decision.evidence.append(f"Failed: {run.failed}")
        decision.evidence.append(f"Infrastructure failures: {run.infrastructure_failures}")

        # Add risks
        if run.infrastructure_failures > 0:
            decision.risks.append(
                f"{run.infrastructure_failures} infrastructure failure(s)"
            )

        return decision


def generate_reality_report(run: RealityRun, format: str = "text") -> str:
    """Convenience function to generate a reality report."""
    reporter = RealityReporter()
    if format == "json":
        import json
        return json.dumps(reporter.generate_json_report(run), indent=2)
    return reporter.generate_text_report(run)
