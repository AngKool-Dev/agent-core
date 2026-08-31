"""UX formatting utilities."""

from typing import List, Optional

from argus.ux.models import (
    EventSeverity,
    LifecyclePhase,
    PlanStep,
    ProviderStatus,
    SecurityStatus,
    PerformanceStatus,
    RecoveryStatus,
    ReviewStatus,
    StepStatus,
    UIEvent,
    VerificationStatus,
)


class UXFormatter:
    """Formats UX data for display."""

    def __init__(self, use_unicode: bool = True, use_color: bool = True):
        self._use_unicode = use_unicode
        self._use_color = use_color

    def format_phase(self, phase: LifecyclePhase) -> str:
        """Format a lifecycle phase."""
        phase_names = {
            LifecyclePhase.IDLE: "Idle",
            LifecyclePhase.UNDERSTAND: "Understanding",
            LifecyclePhase.INVESTIGATE: "Investigating",
            LifecyclePhase.PLAN: "Planning",
            LifecyclePhase.EXECUTE: "Executing",
            LifecyclePhase.VERIFY: "Verifying",
            LifecyclePhase.REPLAN: "Replanning",
            LifecyclePhase.RECOVER: "Recovering",
            LifecyclePhase.REPAIR: "Repairing",
            LifecyclePhase.REVIEW: "Reviewing",
            LifecyclePhase.FINALIZE: "Finalizing",
        }
        return phase_names.get(phase, phase.value)

    def format_step_status(self, status: StepStatus) -> str:
        """Format a step status indicator."""
        if self._use_unicode:
            symbols = {
                StepStatus.PENDING: "○",
                StepStatus.ACTIVE: "●",
                StepStatus.COMPLETED: "✓",
                StepStatus.FAILED: "✗",
                StepStatus.SKIPPED: "⊘",
                StepStatus.BLOCKED: "⊘",
                StepStatus.WAITING_APPROVAL: "?",
            }
        else:
            symbols = {
                StepStatus.PENDING: "[ ]",
                StepStatus.ACTIVE: "[>]",
                StepStatus.COMPLETED: "[✓]",
                StepStatus.FAILED: "[✗]",
                StepStatus.SKIPPED: "[-]",
                StepStatus.BLOCKED: "[!]",
                StepStatus.WAITING_APPROVAL: "[?]",
            }
        return symbols.get(status, "[?]")

    def format_event_severity(self, severity: EventSeverity) -> str:
        """Format an event severity."""
        if self._use_unicode:
            symbols = {
                EventSeverity.DEBUG: "○",
                EventSeverity.INFO: "●",
                EventSeverity.SUCCESS: "✓",
                EventSeverity.WARNING: "⚠",
                EventSeverity.ERROR: "✗",
                EventSeverity.CRITICAL: "!!",
            }
        else:
            symbols = {
                EventSeverity.DEBUG: "[.]",
                EventSeverity.INFO: "[i]",
                EventSeverity.SUCCESS: "[+]",
                EventSeverity.WARNING: "[!]",
                EventSeverity.ERROR: "[x]",
                EventSeverity.CRITICAL: "[!!]",
            }
        return symbols.get(severity, "[?]")

    def format_provider_status(self, status: ProviderStatus) -> str:
        """Format provider status for display."""
        lines = [
            f"Provider: {status.provider}",
            f"Model: {status.model}",
            f"Health: {status.health}",
            f"Circuit: {status.circuit_state}",
            f"Latency: {status.latency_seconds:.2f}s",
            f"Retries: {status.retry_count}",
            f"Fallbacks: {status.fallback_count}",
        ]
        return "\n".join(lines)

    def format_security_status(self, status: SecurityStatus) -> str:
        """Format security status for display."""
        lines = [
            f"Allowed: {status.allowed_count}",
            f"Approvals: {status.approval_count}",
            f"Denied: {status.denied_count}",
            f"Injections: {status.injection_attempts}",
            f"Risk: {status.risk_level.upper()}",
        ]
        return "\n".join(lines)

    def format_performance_status(self, status: PerformanceStatus) -> str:
        """Format performance status for display."""
        lines = [
            f"Runtime: {status.runtime_seconds:.1f}s",
            f"Active ops: {status.active_operations}",
            f"Tool calls: {status.tool_calls}",
            f"Queue: {status.queue_size}",
            f"Tokens: {status.tokens_used}",
            f"Retries: {status.retry_count}",
            f"Recovery: {status.recovery_count}",
        ]
        return "\n".join(lines)

    def format_verification_status(self, status: VerificationStatus) -> str:
        """Format verification status for display."""
        lines = []
        for criterion, passed in status.criteria.items():
            symbol = "✓" if passed else "✗"
            lines.append(f"  {symbol} {criterion}")
        lines.append(f"\n{status.passed}/{status.total} PASS")
        lines.append(f"Confidence: {status.confidence:.2f}")
        return "\n".join(lines)

    def format_recovery_status(self, status: RecoveryStatus) -> str:
        """Format recovery status for display."""
        lines = [
            f"Attempts: {status.attempts} / {status.max_attempts}",
            f"Replans: {status.replans}",
            f"Repairs: {status.repairs}",
        ]
        if status.last_failure:
            lines.append(f"Last failure: {status.last_failure}")
        if status.last_action:
            lines.append(f"Last action: {status.last_action}")
        lines.append(f"Status: {status.status}")
        return "\n".join(lines)

    def format_review_status(self, status: ReviewStatus) -> str:
        """Format review status for display."""
        lines = []
        for finding, result in status.findings.items():
            symbol = "✓" if result == "pass" else "✗"
            lines.append(f"  {symbol} {finding}")
        lines.append(f"\n{status.passed}/{status.total} PASS")
        lines.append(f"Verdict: {status.final_verdict}")
        return "\n".join(lines)

    def format_event(self, event: UIEvent) -> str:
        """Format a UI event for display."""
        severity = self.format_event_severity(event.severity)
        return f"{severity} {event.message}"

    def format_step(self, step: PlanStep, index: int) -> str:
        """Format a plan step."""
        status = self.format_step_status(step.status)
        return f"{status} {index + 1}. {step.objective}"
