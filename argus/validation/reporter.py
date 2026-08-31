"""Validation reporter for ARGUS real-world scenarios."""

from typing import Dict, List, Optional

from argus.validation.evaluator import ValidationEvaluator
from argus.validation.models import (
    OutcomeType,
    ValidationResult,
    ValidationRun,
    ValidationStatus,
)


class ValidationReporter:
    """Generates validation reports."""

    def __init__(self, evaluator: Optional[ValidationEvaluator] = None):
        self._evaluator = evaluator or ValidationEvaluator()

    def generate_text_report(self, run: ValidationRun) -> str:
        """Generate a text-based validation report."""
        evaluation = self._evaluator.evaluate_run(run)
        summary = evaluation["summary"]
        lines = []

        lines.append("=" * 70)
        lines.append("ARGUS VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Run ID:           {run.run_id}")
        lines.append(f"Total Scenarios:  {summary['total']}")
        lines.append(f"Passed:           {summary['passed']}")
        lines.append(f"Failed:           {summary['failed']}")
        lines.append(f"Errors:           {summary['errors']}")
        lines.append(f"Pass Rate:        {summary['pass_rate']:.1%}")
        lines.append(f"Total Duration:   {summary['total_duration']:.2f}s")
        if "avg_duration" in summary:
            lines.append(f"Avg Duration:     {summary['avg_duration']:.2f}s")
        lines.append("")

        # Outcome distribution
        lines.append("OUTCOME DISTRIBUTION")
        lines.append("-" * 40)
        for outcome, count in evaluation["by_outcome"].items():
            lines.append(f"  {outcome}: {count}")
        lines.append("")

        # Scenario results
        lines.append("SCENARIO RESULTS")
        lines.append("-" * 40)
        for scenario_id, result in run.scenario_results.items():
            status_icon = "PASS" if result.status == ValidationStatus.PASSED else "FAIL"
            lines.append(f"  [{status_icon}] {scenario_id}")
            lines.append(f"    Outcome: {result.outcome.value}")
            lines.append(f"    Duration: {result.duration_seconds:.2f}s")
            lines.append(f"    Tool Calls: {result.tool_call_count}")
            if result.errors:
                lines.append(f"    Errors: {', '.join(result.errors[:3])}")
            if result.contract_violations:
                violations = [v.value for v in result.contract_violations]
                lines.append(f"    Violations: {', '.join(violations)}")
            lines.append("")

        # Failures detail
        failures = evaluation["failures"]
        if failures:
            lines.append("FAILURE DETAILS")
            lines.append("-" * 40)
            for failure in failures:
                lines.append(f"  Scenario: {failure['scenario_id']}")
                lines.append(f"    Status: {failure['status']}")
                lines.append(f"    Outcome: {failure['outcome']}")
                if failure["errors"]:
                    lines.append(f"    Errors: {', '.join(failure['errors'][:3])}")
                if failure["contract_violations"]:
                    lines.append(f"    Violations: {', '.join(failure['contract_violations'])}")
                lines.append("")

        # Contract compliance
        compliance = evaluation["contract_compliance"]
        lines.append("CONTRACT COMPLIANCE")
        lines.append("-" * 40)
        lines.append(f"  Compliant:     {compliance['compliant']}")
        lines.append(f"  Non-Compliant: {compliance['non_compliant']}")
        lines.append(f"  Compliance Rate: {compliance['compliance_rate']:.1%}")
        lines.append("")

        # Recommendations
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 40)
        for rec in evaluation["recommendations"]:
            lines.append(f"  - {rec}")
        lines.append("")

        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_markdown_report(self, run: ValidationRun) -> str:
        """Generate a markdown validation report."""
        evaluation = self._evaluator.evaluate_run(run)
        summary = evaluation["summary"]
        lines = []

        lines.append("# ARGUS Validation Report")
        lines.append("")
        lines.append(f"**Run ID:** `{run.run_id}`")
        lines.append("")

        # Summary table
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Scenarios | {summary['total']} |")
        lines.append(f"| Passed | {summary['passed']} |")
        lines.append(f"| Failed | {summary['failed']} |")
        lines.append(f"| Errors | {summary['errors']} |")
        lines.append(f"| Pass Rate | {summary['pass_rate']:.1%} |")
        lines.append(f"| Total Duration | {summary['total_duration']:.2f}s |")
        lines.append("")

        # Outcome distribution
        lines.append("## Outcome Distribution")
        lines.append("")
        lines.append("| Outcome | Count |")
        lines.append("|---------|-------|")
        for outcome, count in evaluation["by_outcome"].items():
            lines.append(f"| {outcome} | {count} |")
        lines.append("")

        # Scenario results
        lines.append("## Scenario Results")
        lines.append("")
        lines.append("| Scenario | Status | Outcome | Duration | Tool Calls |")
        lines.append("|----------|--------|---------|----------|------------|")
        for scenario_id, result in run.scenario_results.items():
            status = "PASS" if result.status == ValidationStatus.PASSED else "FAIL"
            lines.append(
                f"| {scenario_id} | {status} | {result.outcome.value} | "
                f"{result.duration_seconds:.2f}s | {result.tool_call_count} |"
            )
        lines.append("")

        # Failures
        failures = evaluation["failures"]
        if failures:
            lines.append("## Failure Details")
            lines.append("")
            for failure in failures:
                lines.append(f"### {failure['scenario_id']}")
                lines.append("")
                lines.append(f"- **Status:** {failure['status']}")
                lines.append(f"- **Outcome:** {failure['outcome']}")
                if failure["errors"]:
                    lines.append(f"- **Errors:** {', '.join(failure['errors'][:3])}")
                lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")
        for rec in evaluation["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

        return "\n".join(lines)

    def generate_json_report(self, run: ValidationRun) -> Dict:
        """Generate a JSON validation report."""
        evaluation = self._evaluator.evaluate_run(run)
        return {
            "run_id": run.run_id,
            "report_type": "validation",
            "evaluation": evaluation,
            "run_data": run.to_dict(),
        }


def generate_validation_report(run: ValidationRun, format: str = "text") -> str:
    """Convenience function to generate a validation report."""
    reporter = ValidationReporter()
    if format == "markdown":
        return reporter.generate_markdown_report(run)
    elif format == "json":
        import json
        return json.dumps(reporter.generate_json_report(run), indent=2)
    return reporter.generate_text_report(run)
