"""Tests for ARGUS Replay consistency checking."""

import pytest

from argus.replay import (
    ReplayRun,
    ReplayEvent,
    RunStatus,
    ReplayConsistencyChecker,
    check_consistency,
)


class TestConsistencyEdgeCases:
    """Edge case tests for consistency checking."""

    def test_empty_run(self):
        run = ReplayRun(run_id="empty")
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert isinstance(issues, list)

    def test_single_event(self):
        run = ReplayRun(
            run_id="single",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_missing_sequence_numbers(self):
        run = ReplayRun(
            run_id="gaps",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                ),
                # Missing sequence 1
                ReplayEvent(
                    sequence=2,
                    event_id="evt-002",
                    timestamp=1002.0,
                    event_type="agent.completed",
                    category="agent",
                    source="agent",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("Missing sequence" in i.description for i in issues)

    def test_cross_run_contamination(self):
        run = ReplayRun(
            run_id="run-a",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                    run_id="run-b",  # Different run_id
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("cross runs" in i.description.lower() or "other runs" in i.description.lower() for i in issues)

    def test_timestamp_decrease(self):
        run = ReplayRun(
            run_id="time-decrease",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                ),
                ReplayEvent(
                    sequence=1,
                    event_id="evt-002",
                    timestamp=999.0,  # Earlier timestamp
                    event_type="agent.completed",
                    category="agent",
                    source="agent",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("Timestamp decreased" in i.description for i in issues)

    def test_impossible_capability_transition(self):
        run = ReplayRun(
            run_id="impossible",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="capability.started",
                    category="capability",
                    source="capability_router",
                    capability="read_file",
                ),
                ReplayEvent(
                    sequence=1,
                    event_id="evt-002",
                    timestamp=1001.0,
                    event_type="capability.started",  # Started again without ending
                    category="capability",
                    source="capability_router",
                    capability="read_file",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("started while in state" in i.description.lower() for i in issues)

    def test_security_denied_then_executed(self):
        run = ReplayRun(
            run_id="deny-exec",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="security.denied",
                    category="security",
                    source="security_kernel",
                    capability="shell.execute",
                ),
                ReplayEvent(
                    sequence=1,
                    event_id="evt-002",
                    timestamp=1001.0,
                    event_type="execution.completed",
                    category="execution",
                    source="execution_engine",
                    capability="shell.execute",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("denial" in i.description.lower() or "denied" in i.description.lower() for i in issues)


class TestConsistencyWithCheckpoints:
    """Test consistency with checkpoints."""

    def test_checkpoint_sequence_consistency(self):
        from argus.replay import ReplayCheckpoint

        run = ReplayRun(
            run_id="cp-test",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                ),
            ],
            checkpoints=[
                ReplayCheckpoint(
                    checkpoint_id="cp-001",
                    sequence=0,
                    timestamp=1000.0,
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0
