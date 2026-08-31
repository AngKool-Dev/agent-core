"""Tests for ARGUS UX controller."""

import threading

import pytest

from argus.ux.controller import UXController
from argus.ux.models import (
    EventSeverity,
    ExecutionPlan,
    LifecyclePhase,
    ProviderStatus,
    SecurityStatus,
    PerformanceStatus,
    RecoveryStatus,
    ReviewStatus,
    StepStatus,
    UIEvent,
    UXConfiguration,
    VerificationStatus,
)
from argus.ux.state import UXState


class TestUXController:
    """Tests for UXController."""

    def test_initial_state(self):
        controller = UXController()
        assert controller.state.current_phase == LifecyclePhase.IDLE
        assert controller.state.plan is None

    def test_start_and_stop(self):
        controller = UXController()
        controller.start()
        assert controller.is_active is True
        controller.stop()
        assert controller.is_active is False

    def test_update_phase(self):
        controller = UXController()
        controller.update_phase(LifecyclePhase.EXECUTE)
        assert controller.state.current_phase == LifecyclePhase.EXECUTE

    def test_update_plan(self):
        controller = UXController()
        plan = ExecutionPlan(run_id="run-001", total_steps=5)
        controller.update_plan(plan)
        assert controller.state.plan.run_id == "run-001"

    def test_update_provider_status(self):
        controller = UXController()
        status = ProviderStatus(provider="openai", model="gpt-4")
        controller.update_provider_status(status)
        assert controller.state.provider_status.provider == "openai"

    def test_update_security_status(self):
        controller = UXController()
        status = SecurityStatus(allowed_count=10, denied_count=2)
        controller.update_security_status(status)
        assert controller.state.security_status.allowed_count == 10

    def test_update_performance_status(self):
        controller = UXController()
        status = PerformanceStatus(runtime_seconds=120.0, tool_calls=15)
        controller.update_performance_status(status)
        assert controller.state.performance_status.runtime_seconds == 120.0

    def test_update_verification_status(self):
        controller = UXController()
        status = VerificationStatus(passed=3, failed=0, total=3)
        controller.update_verification_status(status)
        assert controller.state.verification_status.passed == 3

    def test_update_recovery_status(self):
        controller = UXController()
        status = RecoveryStatus(attempts=1, max_attempts=3)
        controller.update_recovery_status(status)
        assert controller.state.recovery_status.attempts == 1

    def test_update_review_status(self):
        controller = UXController()
        status = ReviewStatus(passed=5, failed=0, total=5)
        controller.update_review_status(status)
        assert controller.state.review_status.passed == 5

    def test_set_error(self):
        controller = UXController()
        controller.set_error("Something went wrong")
        assert controller.state.error_message == "Something went wrong"
        controller.clear_error()
        assert controller.state.error_message is None

    def test_set_status(self):
        controller = UXController()
        controller.set_status("Working...")
        assert controller.state.status_message == "Working..."

    def test_register_render_callback(self):
        controller = UXController()
        callback_called = []

        def on_render():
            callback_called.append(True)

        controller.register_render_callback(on_render)
        controller.update_phase(LifecyclePhase.EXECUTE)
        assert len(callback_called) > 0

    def test_unregister_render_callback(self):
        controller = UXController()
        callback_called = []

        def on_render():
            callback_called.append(True)

        controller.register_render_callback(on_render)
        controller.unregister_render_callback(on_render)
        callback_called.clear()
        controller.update_phase(LifecyclePhase.EXECUTE)
        assert len(callback_called) == 0

    def test_config(self):
        config = UXConfiguration(theme="dark", compact_mode=True)
        controller = UXController(config)
        assert controller.config.theme == "dark"
        assert controller.config.compact_mode is True

    def test_theme_manager(self):
        controller = UXController()
        themes = controller.theme_manager.list_themes()
        assert "default" in themes
        assert "dark" in themes

    def test_formatter(self):
        controller = UXController()
        formatted = controller.formatter.format_phase(LifecyclePhase.EXECUTE)
        assert formatted == "Executing"
