"""Tests for ARGUS UX state management."""

import threading

import pytest

from argus.ux.models import (
    EventSeverity,
    ExecutionPlan,
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
from argus.ux.state import UXState


class TestUXState:
    """Tests for UXState."""

    def test_initial_state(self):
        state = UXState()
        assert state.current_phase == LifecyclePhase.IDLE
        assert state.plan is None
        assert len(state.events) == 0

    def test_current_phase(self):
        state = UXState()
        state.current_phase = LifecyclePhase.EXECUTE
        assert state.current_phase == LifecyclePhase.EXECUTE

    def test_plan(self):
        state = UXState()
        plan = ExecutionPlan(run_id="run-001", total_steps=5)
        state.plan = plan
        assert state.plan is not None
        assert state.plan.run_id == "run-001"

    def test_add_event(self):
        state = UXState()
        event = UIEvent(message="Test event", severity=EventSeverity.INFO)
        state.add_event(event)
        assert len(state.events) == 1
        assert state.events[0].message == "Test event"

    def test_clear_events(self):
        state = UXState()
        state.add_event(UIEvent(message="Event 1"))
        state.add_event(UIEvent(message="Event 2"))
        state.clear_events()
        assert len(state.events) == 0

    def test_provider_status(self):
        state = UXState()
        status = ProviderStatus(provider="openai", model="gpt-4")
        state.provider_status = status
        assert state.provider_status.provider == "openai"

    def test_security_status(self):
        state = UXState()
        status = SecurityStatus(allowed_count=10, denied_count=2)
        state.security_status = status
        assert state.security_status.allowed_count == 10

    def test_performance_status(self):
        state = UXState()
        status = PerformanceStatus(runtime_seconds=120.0, tool_calls=15)
        state.performance_status = status
        assert state.performance_status.runtime_seconds == 120.0

    def test_verification_status(self):
        state = UXState()
        status = VerificationStatus(passed=3, failed=0, total=3)
        state.verification_status = status
        assert state.verification_status.passed == 3

    def test_recovery_status(self):
        state = UXState()
        status = RecoveryStatus(attempts=1, max_attempts=3)
        state.recovery_status = status
        assert state.recovery_status.attempts == 1

    def test_review_status(self):
        state = UXState()
        status = ReviewStatus(passed=5, failed=0, total=5)
        state.review_status = status
        assert state.review_status.passed == 5

    def test_error_message(self):
        state = UXState()
        state.error_message = "Something went wrong"
        assert state.error_message == "Something went wrong"
        state.clear_error()
        assert state.error_message is None

    def test_status_message(self):
        state = UXState()
        state.status_message = "Working..."
        assert state.status_message == "Working..."

    def test_thread_safety(self):
        """Test that state access is thread-safe."""
        state = UXState()
        errors = []

        def writer():
            for i in range(100):
                try:
                    state.add_event(UIEvent(message=f"Event {i}"))
                except Exception as e:
                    errors.append(e)

        def reader():
            for _ in range(100):
                try:
                    _ = state.events
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_event_history_limit(self):
        """Test that event history respects maxlen."""
        from argus.ux.models import UXConfiguration

        config = UXConfiguration(max_event_history=5)
        state = UXState(config)
        for i in range(10):
            state.add_event(UIEvent(message=f"Event {i}"))
        assert len(state.events) == 5
        # Should keep the most recent events
        assert state.events[-1].message == "Event 9"
