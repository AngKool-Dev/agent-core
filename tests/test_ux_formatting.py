"""Tests for ARGUS UX formatting."""

import pytest

from argus.ux.formatting import UXFormatter
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


class TestUXFormatter:
    """Tests for UXFormatter."""

    def setup_method(self):
        self.formatter = UXFormatter(use_unicode=True, use_color=True)

    def test_format_phase(self):
        assert self.formatter.format_phase(LifecyclePhase.IDLE) == "Idle"
        assert self.formatter.format_phase(LifecyclePhase.EXECUTE) == "Executing"
        assert self.formatter.format_phase(LifecyclePhase.VERIFY) == "Verifying"

    def test_format_step_status_unicode(self):
        assert self.formatter.format_step_status(StepStatus.PENDING) == "○"
        assert self.formatter.format_step_status(StepStatus.ACTIVE) == "●"
        assert self.formatter.format_step_status(StepStatus.COMPLETED) == "✓"
        assert self.formatter.format_step_status(StepStatus.FAILED) == "✗"

    def test_format_step_status_ascii(self):
        formatter = UXFormatter(use_unicode=False)
        assert "[ ]" in formatter.format_step_status(StepStatus.PENDING)
        assert "[>]" in formatter.format_step_status(StepStatus.ACTIVE)
        assert "[✓]" in formatter.format_step_status(StepStatus.COMPLETED)
        assert "[✗]" in formatter.format_step_status(StepStatus.FAILED)

    def test_format_event_severity_unicode(self):
        assert self.formatter.format_event_severity(EventSeverity.INFO) == "●"
        assert self.formatter.format_event_severity(EventSeverity.SUCCESS) == "✓"
        assert self.formatter.format_event_severity(EventSeverity.WARNING) == "⚠"
        assert self.formatter.format_event_severity(EventSeverity.ERROR) == "✗"

    def test_format_event_severity_ascii(self):
        formatter = UXFormatter(use_unicode=False)
        assert "[.]" in formatter.format_event_severity(EventSeverity.DEBUG)
        assert "[+]" in formatter.format_event_severity(EventSeverity.SUCCESS)
        assert "[!]" in formatter.format_event_severity(EventSeverity.WARNING)
        assert "[x]" in formatter.format_event_severity(EventSeverity.ERROR)

    def test_format_provider_status(self):
        status = ProviderStatus(
            provider="openai",
            model="gpt-4",
            health="healthy",
            latency_seconds=1.5,
        )
        formatted = self.formatter.format_provider_status(status)
        assert "openai" in formatted
        assert "gpt-4" in formatted
        assert "healthy" in formatted
        assert "1.5" in formatted

    def test_format_security_status(self):
        status = SecurityStatus(
            allowed_count=10,
            denied_count=2,
            risk_level="low",
        )
        formatted = self.formatter.format_security_status(status)
        assert "10" in formatted
        assert "2" in formatted
        assert "LOW" in formatted

    def test_format_performance_status(self):
        status = PerformanceStatus(
            runtime_seconds=120.0,
            tool_calls=15,
            tokens_used=5000,
        )
        formatted = self.formatter.format_performance_status(status)
        assert "120.0" in formatted
        assert "15" in formatted
        assert "5000" in formatted

    def test_format_verification_status(self):
        status = VerificationStatus(
            criteria={"syntax": True, "tests": True, "types": False},
            passed=2,
            failed=1,
            total=3,
            confidence=0.85,
        )
        formatted = self.formatter.format_verification_status(status)
        assert "2/3" in formatted
        assert "0.85" in formatted

    def test_format_recovery_status(self):
        status = RecoveryStatus(
            attempts=2,
            max_attempts=3,
            replans=1,
            last_failure="timeout",
            status="recovering",
        )
        formatted = self.formatter.format_recovery_status(status)
        assert "2 / 3" in formatted
        assert "timeout" in formatted
        assert "recovering" in formatted

    def test_format_review_status(self):
        status = ReviewStatus(
            findings={"requirements": "pass", "security": "pass"},
            passed=2,
            failed=0,
            total=2,
            final_verdict="pass",
        )
        formatted = self.formatter.format_review_status(status)
        assert "2/2" in formatted
        assert "pass" in formatted

    def test_format_event(self):
        event = UIEvent(
            message="Test event",
            severity=EventSeverity.INFO,
        )
        formatted = self.formatter.format_event(event)
        assert "Test event" in formatted

    def test_format_step(self):
        step = PlanStep(
            objective="Fix the bug",
            status=StepStatus.COMPLETED,
        )
        formatted = self.formatter.format_step(step, 0)
        assert "Fix the bug" in formatted
        assert "1" in formatted
