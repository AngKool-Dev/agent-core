"""Tests for ARGUS UX models."""

import pytest

from argus.ux.models import (
    EventSeverity,
    ExecutionPlan,
    LifecyclePhase,
    PanelView,
    PlanStep,
    ProviderStatus,
    SecurityStatus,
    PerformanceStatus,
    RecoveryStatus,
    ReviewStatus,
    SessionInfo,
    StepStatus,
    UIEvent,
    UXConfiguration,
    VerificationStatus,
)


class TestLifecyclePhase:
    """Tests for LifecyclePhase enum."""

    def test_all_phases_exist(self):
        phases = [p.value for p in LifecyclePhase]
        assert "idle" in phases
        assert "execute" in phases
        assert "verify" in phases
        assert "recover" in phases
        assert "review" in phases

    def test_phase_values(self):
        assert LifecyclePhase.IDLE.value == "idle"
        assert LifecyclePhase.EXECUTE.value == "execute"


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_all_statuses_exist(self):
        statuses = [s.value for s in StepStatus]
        assert "pending" in statuses
        assert "active" in statuses
        assert "completed" in statuses
        assert "failed" in statuses
        assert "blocked" in statuses


class TestEventSeverity:
    """Tests for EventSeverity enum."""

    def test_all_severities_exist(self):
        severities = [s.value for s in EventSeverity]
        assert "debug" in severities
        assert "info" in severities
        assert "success" in severities
        assert "warning" in severities
        assert "error" in severities
        assert "critical" in severities


class TestPanelView:
    """Tests for PanelView enum."""

    def test_all_views_exist(self):
        views = [v.value for v in PanelView]
        assert "plan" in views
        assert "providers" in views
        assert "security" in views
        assert "performance" in views
        assert "events" in views


class TestPlanStep:
    """Tests for PlanStep model."""

    def test_create_step(self):
        step = PlanStep(
            step_id="step-1",
            objective="Test objective",
            status=StepStatus.PENDING,
        )
        assert step.step_id == "step-1"
        assert step.objective == "Test objective"
        assert step.status == StepStatus.PENDING

    def test_step_with_capabilities(self):
        step = PlanStep(
            step_id="step-1",
            objective="Test",
            capabilities=["read_file", "write_file"],
        )
        assert len(step.capabilities) == 2


class TestExecutionPlan:
    """Tests for ExecutionPlan model."""

    def test_create_plan(self):
        plan = ExecutionPlan(run_id="run-001", total_steps=5)
        assert plan.run_id == "run-001"
        assert plan.total_steps == 5

    def test_completed_steps(self):
        plan = ExecutionPlan(
            steps=[
                PlanStep(status=StepStatus.COMPLETED),
                PlanStep(status=StepStatus.COMPLETED),
                PlanStep(status=StepStatus.PENDING),
            ]
        )
        assert plan.completed_steps == 2

    def test_failed_steps(self):
        plan = ExecutionPlan(
            steps=[
                PlanStep(status=StepStatus.FAILED),
                PlanStep(status=StepStatus.COMPLETED),
                PlanStep(status=StepStatus.FAILED),
            ]
        )
        assert plan.failed_steps == 2


class TestUIEvent:
    """Tests for UIEvent model."""

    def test_create_event(self):
        event = UIEvent(
            event_id="evt-001",
            event_type="agent",
            severity=EventSeverity.INFO,
            message="Test event",
        )
        assert event.event_id == "evt-001"
        assert event.event_type == "agent"
        assert event.severity == EventSeverity.INFO

    def test_event_with_run_id(self):
        event = UIEvent(
            message="Test",
            run_id="run-001",
            capability_id="cap-001",
        )
        assert event.run_id == "run-001"
        assert event.capability_id == "cap-001"


class TestProviderStatus:
    """Tests for ProviderStatus model."""

    def test_create_status(self):
        status = ProviderStatus(
            provider="openai",
            model="gpt-4",
            health="healthy",
        )
        assert status.provider == "openai"
        assert status.model == "gpt-4"
        assert status.health == "healthy"


class TestSecurityStatus:
    """Tests for SecurityStatus model."""

    def test_create_status(self):
        status = SecurityStatus(
            allowed_count=10,
            denied_count=2,
            risk_level="low",
        )
        assert status.allowed_count == 10
        assert status.denied_count == 2
        assert status.risk_level == "low"


class TestPerformanceStatus:
    """Tests for PerformanceStatus model."""

    def test_create_status(self):
        status = PerformanceStatus(
            runtime_seconds=120.0,
            tool_calls=15,
            tokens_used=5000,
        )
        assert status.runtime_seconds == 120.0
        assert status.tool_calls == 15
        assert status.tokens_used == 5000


class TestVerificationStatus:
    """Tests for VerificationStatus model."""

    def test_create_status(self):
        status = VerificationStatus(
            criteria={"syntax": True, "tests": True, "types": False},
            passed=2,
            failed=1,
            total=3,
            confidence=0.85,
        )
        assert status.passed == 2
        assert status.failed == 1
        assert status.confidence == 0.85


class TestRecoveryStatus:
    """Tests for RecoveryStatus model."""

    def test_create_status(self):
        status = RecoveryStatus(
            attempts=2,
            max_attempts=3,
            replans=1,
            status="recovering",
        )
        assert status.attempts == 2
        assert status.max_attempts == 3
        assert status.status == "recovering"


class TestReviewStatus:
    """Tests for ReviewStatus model."""

    def test_create_status(self):
        status = ReviewStatus(
            findings={"requirements": "pass", "security": "pass"},
            passed=2,
            failed=0,
            total=2,
            final_verdict="pass",
        )
        assert status.passed == 2
        assert status.final_verdict == "pass"


class TestUXConfiguration:
    """Tests for UXConfiguration model."""

    def test_default_config(self):
        config = UXConfiguration()
        assert config.theme == "default"
        assert config.verbosity == "normal"
        assert config.animations is True
        assert config.compact_mode is False

    def test_custom_config(self):
        config = UXConfiguration(
            theme="dark",
            verbosity="quiet",
            compact_mode=True,
        )
        assert config.theme == "dark"
        assert config.verbosity == "quiet"
        assert config.compact_mode is True


class TestSessionInfo:
    """Tests for SessionInfo model."""

    def test_create_session(self):
        session = SessionInfo(
            session_id="sess-001",
            run_id="run-001",
            status="running",
            task_description="Fix the bug",
        )
        assert session.session_id == "sess-001"
        assert session.status == "running"
