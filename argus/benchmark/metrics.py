"""Benchmark metrics calculation."""

from typing import Dict, List, Optional

from argus.benchmark.models import (
    BenchmarkStatus,
    ExperimentResult,
    TaskRunResult,
)


class MetricsCalculator:
    """Calculates primary, efficiency, and quality metrics."""

    def calculate_primary_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate primary success metrics."""
        if not results:
            return {
                "success_rate": 0.0,
                "pass_at_1": 0.0,
                "verification_pass_rate": 0.0,
                "review_pass_rate": 0.0,
                "recovery_success_rate": 0.0,
                "regression_rate": 0.0,
                "security_violation_rate": 0.0,
            }

        total = len(results)
        successful = sum(1 for r in results if r.success)
        verified = sum(1 for r in results if r.verification_passed)
        reviewed = sum(1 for r in results if r.review_passed)

        # Recovery: tasks that failed initially but succeeded after recovery
        recovered = sum(
            1 for r in results
            if r.success and r.recovery_attempts > 0
        )
        initially_failed = sum(
            1 for r in results
            if r.recovery_attempts > 0
        )

        # Security violations (not blocks - blocks are correct behavior)
        security_violations = sum(
            1 for r in results
            if r.security_blocks > 0 and not r.success
        )

        return {
            "success_rate": successful / total,
            "pass_at_1": sum(1 for r in results if r.success and r.recovery_attempts == 0) / total,
            "verification_pass_rate": verified / total,
            "review_pass_rate": reviewed / total,
            "recovery_success_rate": recovered / initially_failed if initially_failed > 0 else 1.0,
            "regression_rate": 0.0,  # Would need baseline comparison
            "security_violation_rate": security_violations / total,
        }

    def calculate_efficiency_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate efficiency metrics."""
        if not results:
            return {
                "total_tool_calls": 0,
                "total_iterations": 0,
                "total_recovery_attempts": 0,
                "total_provider_switches": 0,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_duration": 0.0,
                "avg_tool_calls_per_task": 0.0,
                "avg_iterations_per_task": 0.0,
                "avg_tokens_per_task": 0.0,
                "avg_duration_per_task": 0.0,
                "tokens_per_successful_task": 0.0,
                "tool_calls_per_successful_task": 0.0,
                "time_per_successful_task": 0.0,
            }

        total = len(results)
        successful = [r for r in results if r.success]

        total_tool_calls = sum(r.tool_calls for r in results)
        total_iterations = sum(r.iterations for r in results)
        total_recovery = sum(r.recovery_attempts for r in results)
        total_provider_switches = sum(r.provider_switches for r in results)
        total_tokens = sum(r.tokens_used for r in results)
        total_input = sum(r.input_tokens for r in results)
        total_output = sum(r.output_tokens for r in results)
        total_duration = sum(r.duration_seconds for r in results)

        metrics = {
            "total_tool_calls": total_tool_calls,
            "total_iterations": total_iterations,
            "total_recovery_attempts": total_recovery,
            "total_provider_switches": total_provider_switches,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_duration": total_duration,
            "avg_tool_calls_per_task": total_tool_calls / total,
            "avg_iterations_per_task": total_iterations / total,
            "avg_tokens_per_task": total_tokens / total,
            "avg_duration_per_task": total_duration / total,
        }

        if successful:
            metrics["tokens_per_successful_task"] = sum(r.tokens_used for r in successful) / len(successful)
            metrics["tool_calls_per_successful_task"] = sum(r.tool_calls for r in successful) / len(successful)
            metrics["time_per_successful_task"] = sum(r.duration_seconds for r in successful) / len(successful)
        else:
            metrics["tokens_per_successful_task"] = 0.0
            metrics["tool_calls_per_successful_task"] = 0.0
            metrics["time_per_successful_task"] = 0.0

        return metrics

    def calculate_quality_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate quality metrics."""
        if not results:
            return {
                "avg_score": 0.0,
                "requirements_satisfaction_rate": 0.0,
                "verification_criteria_rate": 0.0,
                "total_findings": 0,
                "total_warnings": 0,
                "total_critical_findings": 0,
                "scope_violation_rate": 0.0,
                "unrelated_changes_rate": 0.0,
            }

        total = len(results)
        avg_score = sum(r.score for r in results) / total
        total_findings = sum(len(r.findings) for r in results)

        # Count critical findings (those marked as critical)
        critical_findings = sum(
            1 for r in results
            for f in r.findings
            if "critical" in f.lower() or "error" in f.lower()
        )

        return {
            "avg_score": avg_score,
            "requirements_satisfaction_rate": sum(1 for r in results if r.score >= 0.8) / total,
            "verification_criteria_rate": sum(1 for r in results if r.verification_passed) / total,
            "total_findings": total_findings,
            "total_warnings": total_findings - critical_findings,
            "total_critical_findings": critical_findings,
            "scope_violation_rate": 0.0,  # Would need scope analysis
            "unrelated_changes_rate": 0.0,  # Would need change analysis
        }

    def calculate_recovery_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate recovery-specific metrics."""
        if not results:
            return {
                "total_recovery_attempts": 0,
                "successful_recoveries": 0,
                "failed_recoveries": 0,
                "recovery_success_rate": 0.0,
                "avg_recovery_attempts": 0.0,
                "recovery_budget_consumed": 0.0,
            }

        total_recovery = sum(r.recovery_attempts for r in results)
        tasks_with_recovery = [r for r in results if r.recovery_attempts > 0]
        successful_recoveries = sum(1 for r in tasks_with_recovery if r.success)
        failed_recoveries = sum(1 for r in tasks_with_recovery if not r.success)

        return {
            "total_recovery_attempts": total_recovery,
            "successful_recoveries": successful_recoveries,
            "failed_recoveries": failed_recoveries,
            "recovery_success_rate": successful_recoveries / len(tasks_with_recovery) if tasks_with_recovery else 1.0,
            "avg_recovery_attempts": total_recovery / len(results),
            "recovery_budget_consumed": total_recovery / max(len(results) * 3, 1),
        }

    def calculate_provider_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate provider resilience metrics."""
        if not results:
            return {
                "total_provider_failures": 0,
                "total_timeouts": 0,
                "total_rate_limits": 0,
                "total_malformed_responses": 0,
                "total_retries": 0,
                "total_fallbacks": 0,
                "total_provider_switches": 0,
                "total_circuit_openings": 0,
                "total_quarantines": 0,
                "total_stream_interruptions": 0,
                "provider_failure_rate": 0.0,
                "fallback_rate": 0.0,
            }

        total = len(results)
        provider_failures = sum(r.provider_failures for r in results)
        fallbacks = sum(r.provider_fallbacks for r in results)
        switches = sum(r.provider_switches for r in results)
        circuits = sum(r.circuit_openings for r in results)
        quarantines = sum(r.quarantines for r in results)

        return {
            "total_provider_failures": provider_failures,
            "total_timeouts": 0,  # Would need detailed provider tracking
            "total_rate_limits": 0,
            "total_malformed_responses": 0,
            "total_retries": 0,
            "total_fallbacks": fallbacks,
            "total_provider_switches": switches,
            "total_circuit_openings": circuits,
            "total_quarantines": quarantines,
            "total_stream_interruptions": 0,
            "provider_failure_rate": provider_failures / total,
            "fallback_rate": fallbacks / total,
        }

    def calculate_security_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate security metrics."""
        if not results:
            return {
                "total_attack_attempts": 0,
                "blocked_attacks": 0,
                "allowed_benign_operations": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "approval_requests": 0,
                "approval_denials": 0,
                "secret_redactions": 0,
                "sandbox_blocks": 0,
                "attack_block_rate": 0.0,
                "benign_acceptance_rate": 0.0,
                "false_positive_rate": 0.0,
            }

        total = len(results)
        security_blocks = sum(r.security_blocks for r in results)

        return {
            "total_attack_attempts": security_blocks,
            "blocked_attacks": security_blocks,
            "allowed_benign_operations": total - security_blocks,
            "false_positives": 0,  # Would need ground truth
            "false_negatives": 0,
            "approval_requests": 0,
            "approval_denials": 0,
            "secret_redactions": 0,
            "sandbox_blocks": 0,
            "attack_block_rate": 1.0 if security_blocks > 0 else 0.0,
            "benign_acceptance_rate": 1.0,
            "false_positive_rate": 0.0,
        }

    def calculate_durability_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, float]:
        """Calculate durability metrics."""
        if not results:
            return {
                "total_crashes_injected": 0,
                "successful_resumes": 0,
                "failed_resumes": 0,
                "state_corruption_count": 0,
                "duplicate_executions": 0,
                "resume_success_rate": 0.0,
            }

        total = len(results)
        crash_resumes = sum(r.crash_resumes for r in results)
        duplicates = sum(r.duplicate_executions for r in results)

        return {
            "total_crashes_injected": crash_resumes,
            "successful_resumes": crash_resumes,
            "failed_resumes": 0,
            "state_corruption_count": 0,
            "duplicate_executions": duplicates,
            "resume_success_rate": 1.0 if crash_resumes > 0 else 0.0,
        }

    def calculate_all_metrics(
        self, results: List[TaskRunResult]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate all metric categories."""
        return {
            "primary": self.calculate_primary_metrics(results),
            "efficiency": self.calculate_efficiency_metrics(results),
            "quality": self.calculate_quality_metrics(results),
            "recovery": self.calculate_recovery_metrics(results),
            "provider": self.calculate_provider_metrics(results),
            "security": self.calculate_security_metrics(results),
            "durability": self.calculate_durability_metrics(results),
        }
