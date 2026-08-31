"""Validation evaluator for ARGUS real-world scenarios."""

from typing import Dict, List, Optional

from argus.validation.models import (
    OutcomeType,
    ValidationCategory,
    ValidationResult,
    ValidationRun,
    ValidationStatus,
    ValidationTier,
)


class ValidationEvaluator:
    """Evaluates validation results and computes aggregate metrics."""

    def evaluate_run(self, run: ValidationRun) -> Dict:
        """Evaluate a complete validation run."""
        evaluation = {
            "run_id": run.run_id,
            "summary": self._compute_summary(run),
            "by_tier": self._compute_by_tier(run),
            "by_category": self._compute_by_category(run),
            "by_outcome": self._compute_by_outcome(run),
            "failures": self._compute_failures(run),
            "contract_compliance": self._compute_contract_compliance(run),
            "recommendations": self._generate_recommendations(run),
        }
        return evaluation

    def _compute_summary(self, run: ValidationRun) -> Dict:
        """Compute summary statistics."""
        total = run.total_scenarios
        if total == 0:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "pass_rate": 0.0,
                "total_duration": 0.0,
            }

        return {
            "total": total,
            "passed": run.passed,
            "failed": run.failed,
            "errors": run.errors,
            "skipped": run.skipped,
            "pass_rate": run.passed / total,
            "total_duration": run.total_duration,
            "avg_duration": run.total_duration / total if total > 0 else 0,
        }

    def _compute_by_tier(self, run: ValidationRun) -> Dict:
        """Compute metrics grouped by tier."""
        tier_results: Dict[str, List[ValidationResult]] = {}

        for result in run.scenario_results.values():
            scenario_tier = "unknown"
            # Extract tier from scenario metadata if available
            if "tier" in result.metadata:
                scenario_tier = result.metadata["tier"]

            if scenario_tier not in tier_results:
                tier_results[scenario_tier] = []
            tier_results[scenario_tier].append(result)

        tier_metrics = {}
        for tier, results in tier_results.items():
            passed = sum(1 for r in results if r.status == ValidationStatus.PASSED)
            tier_metrics[tier] = {
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
                "pass_rate": passed / len(results) if results else 0,
                "avg_duration": sum(r.duration_seconds for r in results) / len(results) if results else 0,
            }

        return tier_metrics

    def _compute_by_category(self, run: ValidationRun) -> Dict:
        """Compute metrics grouped by category."""
        category_results: Dict[str, List[ValidationResult]] = {}

        for result in run.scenario_results.values():
            category = result.metadata.get("category", "unknown")
            if category not in category_results:
                category_results[category] = []
            category_results[category].append(result)

        category_metrics = {}
        for category, results in category_results.items():
            passed = sum(1 for r in results if r.status == ValidationStatus.PASSED)
            category_metrics[category] = {
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
                "pass_rate": passed / len(results) if results else 0,
            }

        return category_metrics

    def _compute_by_outcome(self, run: ValidationRun) -> Dict:
        """Compute distribution of outcomes."""
        outcome_counts: Dict[str, int] = {}

        for result in run.scenario_results.values():
            outcome = result.outcome.value
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

        return outcome_counts

    def _compute_failures(self, run: ValidationRun) -> List[Dict]:
        """Compute failure analysis."""
        failures = []

        for scenario_id, result in run.scenario_results.items():
            if result.status != ValidationStatus.PASSED:
                failure = {
                    "scenario_id": scenario_id,
                    "status": result.status.value,
                    "outcome": result.outcome.value,
                    "errors": result.errors,
                    "contract_violations": [v.value for v in result.contract_violations],
                    "verification_results": result.verification_results,
                }
                failures.append(failure)

        return failures

    def _compute_contract_compliance(self, run: ValidationRun) -> Dict:
        """Compute contract compliance metrics."""
        total = len(run.scenario_results)
        if total == 0:
            return {"compliant": 0, "non_compliant": 0, "compliance_rate": 0.0}

        compliant = sum(
            1 for r in run.scenario_results.values() if not r.contract_violations
        )

        return {
            "compliant": compliant,
            "non_compliant": total - compliant,
            "compliance_rate": compliant / total,
        }

    def _generate_recommendations(self, run: ValidationRun) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        # Check overall pass rate
        if run.total_scenarios > 0:
            pass_rate = run.passed / run.total_scenarios
            if pass_rate < 0.5:
                recommendations.append(
                    "CRITICAL: Overall pass rate is below 50%. "
                    "The agent requires significant improvement before release."
                )
            elif pass_rate < 0.8:
                recommendations.append(
                    "WARNING: Overall pass rate is below 80%. "
                    "Consider addressing failed scenarios before release."
                )

        # Check for timeout issues
        timeouts = sum(
            1 for r in run.scenario_results.values()
            if r.status == ValidationStatus.TIMED_OUT
        )
        if timeouts > 0:
            recommendations.append(
                f"{timeouts} scenario(s) timed out. Consider increasing timeouts or "
                "optimizing agent performance."
            )

        # Check for contract violations
        violations = sum(
            len(r.contract_violations) for r in run.scenario_results.values()
        )
        if violations > 0:
            recommendations.append(
                f"{violations} contract violation(s) detected. "
                "Review contract compliance for production readiness."
            )

        # Check for security issues
        security_failures = sum(
            1 for r in run.scenario_results.values()
            if r.outcome == OutcomeType.SECURITY_BLOCKED
        )
        if security_failures > 0:
            recommendations.append(
                f"{security_failures} scenario(s) blocked by security policy. "
                "Review security boundaries."
            )

        # Check for recovery issues
        recovery_failures = sum(
            1 for r in run.scenario_results.values()
            if r.recovery_attempts > 0 and r.outcome != OutcomeType.RECOVERY_SUCCESS
        )
        if recovery_failures > 0:
            recommendations.append(
                f"{recovery_failures} scenario(s) failed recovery. "
                "Improve recovery strategies."
            )

        if not recommendations:
            recommendations.append(
                "All validation scenarios passed. Agent is ready for release."
            )

        return recommendations

    def compare_runs(self, run1: ValidationRun, run2: ValidationRun) -> Dict:
        """Compare two validation runs."""
        return {
            "run1_id": run1.run_id,
            "run2_id": run2.run_id,
            "pass_rate_delta": run1.success_rate - run2.success_rate,
            "duration_delta": run1.total_duration - run2.total_duration,
            "passed_delta": run1.passed - run2.passed,
            "failed_delta": run1.failed - run2.failed,
        }


def evaluate_validation_run(run: ValidationRun) -> Dict:
    """Convenience function to evaluate a validation run."""
    evaluator = ValidationEvaluator()
    return evaluator.evaluate_run(run)
