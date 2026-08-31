"""Tests for ARGUS Replay + Phase 19 Harness integration."""

import pytest

from argus.replay import (
    ReplayRun,
    ReplayEvent,
    RunStatus,
    ForensicReport,
)


class TestHarnessReplayIntegration:
    """Integration tests between replay and benchmark harness."""

    def test_capture_replay_from_task_result(self):
        """Test capturing replay data from a task result."""
        from argus.harness import BenchmarkTask, TaskState, SuccessCriteria, TaskCategory, TaskDifficulty, TaskLanguage

        task = BenchmarkTask(
            task_id="replay-test",
            name="Replay Test",
            description="Test replay capture",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={"test.py": "original"}),
            success_criteria=SuccessCriteria(),
        )

        # Simulate a task result
        from argus.harness import TaskResult
        result = TaskResult(
            task_id="replay-test",
            run_id="run-test-123",
            success=False,
            status="failed",
            duration_seconds=1.0,
        )

        # Create runner and capture replay
        from argus.harness import BenchmarkRunner
        runner = BenchmarkRunner()
        replay_run = runner._capture_replay_data("run-test-123", task, result)

        # Should return None since no events were emitted
        assert replay_run is None or isinstance(replay_run, ReplayRun)

    def test_forensic_report_from_benchmark_run(self):
        """Test generating forensic report from a benchmark run."""
        run = ReplayRun(
            run_id="bench-123",
            task="Fix the bug",
            status=RunStatus.COMPLETE,
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                    run_id="bench-123",
                ),
                ReplayEvent(
                    sequence=1,
                    event_id="evt-002",
                    timestamp=1005.0,
                    event_type="agent.completed",
                    category="agent",
                    source="agent",
                    status="completed",
                    run_id="bench-123",
                ),
            ],
        )

        report = ForensicReport(run)
        result = report.generate()

        assert result["overview"]["run_id"] == "bench-123"
        assert result["overview"]["status"] == "complete"

    def test_run_with_replay_capture(self):
        """Test the full run_task_with_replay flow."""
        from argus.harness import BenchmarkTask, TaskState, SuccessCriteria, TaskCategory, TaskDifficulty, TaskLanguage, BenchmarkRunner

        task = BenchmarkTask(
            task_id="full-replay-test",
            name="Full Replay Test",
            description="Test full replay capture",
            category=TaskCategory.FIX_FAILING_TEST,
            difficulty=TaskDifficulty.EASY,
            language=TaskLanguage.PYTHON,
            initial_state=TaskState(files={"test.py": "print('hello')"}),
            success_criteria=SuccessCriteria(),
        )

        runner = BenchmarkRunner()
        result, replay_run, forensic_report = runner.run_task_with_replay(task)

        assert result.task_id == "full-replay-test"
        # replay_run may be None if no events captured
        # forensic_report may be None if replay_run is None


class TestReplayDeterminismWithHarness:
    """Test determinism of replay with harness data."""

    def test_same_events_same_timeline(self):
        """Same events should produce same timeline."""
        from argus.replay import ReplayTimeline

        events = [
            ReplayEvent(
                sequence=i,
                event_id=f"evt-{i:03d}",
                timestamp=1000.0 + i,
                event_type="capability.started",
                category="capability",
                source="capability_router",
            )
            for i in range(10)
        ]

        run = ReplayRun(run_id="det-test", events=events)

        timeline1 = ReplayTimeline(run)
        timeline2 = ReplayTimeline(run)

        entries1 = [(e.sequence, e.event_type) for e in timeline1.all()]
        entries2 = [(e.sequence, e.event_type) for e in timeline2.all()]

        assert entries1 == entries2

    def test_same_events_same_state(self):
        """Same events should produce same reconstructed state."""
        from argus.replay import StateReducer

        events = [
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
                timestamp=1001.0,
                event_type="agent.completed",
                category="agent",
                source="agent",
                status="completed",
            ),
        ]

        run = ReplayRun(run_id="det-state", events=events)

        reducer1 = StateReducer()
        state1 = reducer1.reduce(run)

        reducer2 = StateReducer()
        state2 = reducer2.reduce(run)

        assert state1 == state2

    def test_serialized_replay_comparison(self):
        """Serialized replay should be identical for same input."""
        from argus.replay import ReplayTimeline

        events = [
            ReplayEvent(
                sequence=i,
                event_id=f"evt-{i:03d}",
                timestamp=1000.0 + i,
                event_type="test.event",
                category="test",
                source="test",
            )
            for i in range(5)
        ]

        run = ReplayRun(run_id="ser-test", events=events)

        timeline1 = ReplayTimeline(run)
        entries1 = [e.to_dict() for e in timeline1.all()]

        timeline2 = ReplayTimeline(run)
        entries2 = [e.to_dict() for e in timeline2.all()]

        assert entries1 == entries2
