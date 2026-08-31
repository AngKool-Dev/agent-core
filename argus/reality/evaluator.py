"""Reality validation evaluator for ARGUS qualification."""

from typing import Any, Dict, List

from argus.reality.models import (
    FailureCategory,
    RealityRun,
    RealityStatus,
)


class RealityEvaluator:
    """Evaluates reality validation results."""

    def evaluate(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate a complete reality run."""
        return {
            "summary": self._compute_summary(run),
            "providers": self._evaluate_providers(run),
            "mcp": self._evaluate_mcp(run),
            "subprocess": self._evaluate_subprocess(run),
            "windows": self._evaluate_windows(run),
            "secrets": self._evaluate_secrets(run),
            "invariants": self._evaluate_invariants(run),
            "scenarios": self._evaluate_scenarios(run),
            "recommendations": self._generate_recommendations(run),
        }

    def _compute_summary(self, run: RealityRun) -> Dict[str, Any]:
        """Compute summary statistics."""
        return {
            "total_checks": run.total_checks,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "inconclusive": run.inconclusive,
            "infrastructure_failures": run.infrastructure_failures,
            "pass_rate": run.pass_rate,
            "total_duration": run.total_duration,
        }

    def _evaluate_providers(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate provider results."""
        if not run.provider_results:
            return {"status": "not_tested", "providers": {}}

        providers = {}
        for name, result in run.provider_results.items():
            providers[name] = {
                "availability": result.availability.value,
                "lifecycle_stage": result.lifecycle_stage,
                "duration_ms": result.duration_ms,
            }

        available = sum(
            1 for r in run.provider_results.values()
            if r.availability.value == "available"
        )

        return {
            "status": "tested",
            "total": len(run.provider_results),
            "available": available,
            "providers": providers,
        }

    def _evaluate_mcp(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate MCP results."""
        if not run.mcp_results:
            return {"status": "not_tested", "checks": {}}

        checks = {}
        for name, result in run.mcp_results.items():
            checks[name] = {
                "status": result.status.value,
                "lifecycle_stage": result.lifecycle_stage,
                "security_passed": result.security_passed,
            }

        passed = sum(
            1 for r in run.mcp_results.values()
            if r.status == RealityStatus.PASSED
        )

        return {
            "status": "tested",
            "total": len(run.mcp_results),
            "passed": passed,
            "checks": checks,
        }

    def _evaluate_subprocess(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate subprocess results."""
        if not run.subprocess_results:
            return {"status": "not_tested", "checks": {}}

        checks = {}
        for name, result in run.subprocess_results.items():
            checks[name] = {
                "status": result.status.value,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "cancelled": result.cancelled,
            }

        passed = sum(
            1 for r in run.subprocess_results.values()
            if r.status == RealityStatus.PASSED
        )

        return {
            "status": "tested",
            "total": len(run.subprocess_results),
            "passed": passed,
            "checks": checks,
        }

    def _evaluate_windows(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate Windows results."""
        if not run.windows_results:
            return {"status": "not_tested", "checks": {}}

        checks = {}
        for name, result in run.windows_results.items():
            checks[name] = {
                "status": result.status.value,
                "security_scope_maintained": result.security_scope_maintained,
            }

        passed = sum(
            1 for r in run.windows_results.values()
            if r.status == RealityStatus.PASSED
        )

        return {
            "status": "tested",
            "total": len(run.windows_results),
            "passed": passed,
            "checks": checks,
        }

    def _evaluate_secrets(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate secret safety results."""
        if not run.secret_canary_results:
            return {"status": "not_tested", "checks": {}}

        checks = {}
        canary_found = False
        for name, result in run.secret_canary_results.items():
            checks[name] = {
                "status": result.status.value,
                "canary_detected": result.canary_detected,
                "redaction_effective": result.redaction_effective,
            }
            if result.canary_detected:
                canary_found = True

        return {
            "status": "tested",
            "total": len(run.secret_canary_results),
            "canary_found_anywhere": canary_found,
            "checks": checks,
        }

    def _evaluate_invariants(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate invariant results."""
        if not run.invariant_results:
            return {"status": "not_tested", "invariants": {}}

        invariants = {}
        for name, result in run.invariant_results.items():
            invariants[name] = {
                "passed": result.passed,
                "description": result.description,
                "evidence": result.evidence,
            }

        passed = sum(
            1 for r in run.invariant_results.values()
            if r.passed
        )

        return {
            "status": "tested",
            "total": len(run.invariant_results),
            "passed": passed,
            "invariants": invariants,
        }

    def _evaluate_scenarios(self, run: RealityRun) -> Dict[str, Any]:
        """Evaluate scenario results."""
        if not run.scenario_results:
            return {"status": "not_tested", "scenarios": {}}

        scenarios = {}
        for name, result in run.scenario_results.items():
            scenarios[name] = {
                "status": result.status.value,
                "failure_category": result.failure_category.value,
                "duration_seconds": result.duration_seconds,
            }

        passed = sum(
            1 for r in run.scenario_results.values()
            if r.status == RealityStatus.PASSED
        )
        infrastructure = sum(
            1 for r in run.scenario_results.values()
            if r.failure_category == FailureCategory.INFRASTRUCTURE_FAILURE
        )

        return {
            "status": "tested",
            "total": len(run.scenario_results),
            "passed": passed,
            "infrastructure_failures": infrastructure,
            "scenarios": scenarios,
        }

    def _generate_recommendations(self, run: RealityRun) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []

        # Check overall pass rate
        if run.total_checks > 0:
            pass_rate = run.passed / run.total_checks
            if pass_rate < 0.5:
                recommendations.append(
                    "CRITICAL: Overall pass rate below 50%. "
                    "ARGUS requires significant improvement before release."
                )
            elif pass_rate < 0.8:
                recommendations.append(
                    "WARNING: Overall pass rate below 80%. "
                    "Consider addressing failed checks before release."
                )

        # Check invariants
        failed_invariants = [
            name for name, r in run.invariant_results.items() if not r.passed
        ]
        if failed_invariants:
            recommendations.append(
                f"CRITICAL: Failed invariants: {', '.join(failed_invariants)}"
            )

        # Check secret safety
        canary_found = any(
            r.canary_detected for r in run.secret_canary_results.values()
        )
        if canary_found:
            recommendations.append(
                "CRITICAL: Secret canary detected in artifacts. "
                "Secret redaction is not working correctly."
            )

        # Check infrastructure failures
        if run.infrastructure_failures > 0:
            recommendations.append(
                f"{run.infrastructure_failures} infrastructure failure(s) detected. "
                "These are not agent failures but may affect reliability."
            )

        if not recommendations:
            recommendations.append(
                "All reality validation checks passed. "
                "ARGUS is ready for release."
            )

        return recommendations


def evaluate_reality_run(run: RealityRun) -> Dict[str, Any]:
    """Convenience function to evaluate a reality run."""
    evaluator = RealityEvaluator()
    return evaluator.evaluate(run)
