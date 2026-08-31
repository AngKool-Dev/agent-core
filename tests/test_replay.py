"""Tests for ARGUS Replay system."""

import time
import pytest

from argus.replay import (
    EventIntegrity,
    ExecutionNode,
    ReplayCheckpoint,
    ReplayEvent,
    ReplayRun,
    ReplaySnapshot,
    RecoveryAction,
    ReviewResult,
    RunStatus,
    SecurityDecision,
    StateDiff,
    TimelineEntry,
    VerificationResult,
    ConsistencyIssue,
)
from argus.replay.loader import ReplayLoader, ReplayLoadError, load_run, load_partial_run
from argus.replay.timeline import ReplayTimeline
from argus.replay.reducer import StateReducer, reduce_run
from argus.replay.checkpoint import CheckpointManager
from argus.replay.replay import ReplayEngine, ReplayResult
from argus.replay.tree import build_execution_tree, format_execution_tree
from argus.replay.diff import ReplayDiff
from argus.replay.consistency import ReplayConsistencyChecker, check_consistency
from argus.replay.forensic import ForensicReport, generate_forensic_report


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_event():
    """Create a sample replay event."""
    return ReplayEvent(
        sequence=0,
        event_id="evt-001",
        timestamp=1000.0,
        event_type="agent.started",
        category="agent",
        source="agent",
        run_id="run-123",
        session_id="session-456",
    )


@pytest.fixture
def sample_events():
    """Create a list of sample events."""
    return [
        ReplayEvent(
            sequence=0,
            event_id="evt-001",
            timestamp=1000.0,
            event_type="agent.started",
            category="agent",
            source="agent",
            run_id="run-123",
        ),
        ReplayEvent(
            sequence=1,
            event_id="evt-002",
            timestamp=1001.0,
            event_type="task.received",
            category="task",
            source="agent",
            run_id="run-123",
            payload={"task": "Fix the bug"},
        ),
        ReplayEvent(
            sequence=2,
            event_id="evt-003",
            timestamp=1002.0,
            event_type="plan.created",
            category="task",
            source="agent",
            run_id="run-123",
            metadata={"steps": ["investigate", "implement", "verify"]},
        ),
        ReplayEvent(
            sequence=3,
            event_id="evt-004",
            timestamp=1003.0,
            event_type="capability.started",
            category="capability",
            source="capability_router",
            run_id="run-123",
            capability="read_file",
        ),
        ReplayEvent(
            sequence=4,
            event_id="evt-005",
            timestamp=1004.0,
            event_type="capability.completed",
            category="capability",
            source="capability_router",
            run_id="run-123",
            capability="read_file",
            status="completed",
        ),
        ReplayEvent(
            sequence=5,
            event_id="evt-006",
            timestamp=1005.0,
            event_type="agent.completed",
            category="agent",
            source="agent",
            run_id="run-123",
            status="completed",
        ),
    ]


@pytest.fixture
def sample_run(sample_events):
    """Create a sample replay run."""
    return ReplayRun(
        run_id="run-123",
        session_id="session-456",
        task="Fix the bug",
        started_at=1000.0,
        ended_at=1005.0,
        status=RunStatus.COMPLETE,
        events=sample_events,
    )


@pytest.fixture
def partial_run():
    """Create a partial (incomplete) run."""
    events = [
        ReplayEvent(
            sequence=0,
            event_id="evt-001",
            timestamp=1000.0,
            event_type="agent.started",
            category="agent",
            source="agent",
            run_id="run-partial",
        ),
        ReplayEvent(
            sequence=1,
            event_id="evt-002",
            timestamp=1001.0,
            event_type="capability.started",
            category="capability",
            source="capability_router",
            run_id="run-partial",
            capability="read_file",
        ),
        # No completion event - simulates crash
    ]
    return ReplayRun(
        run_id="run-partial",
        task="Incomplete task",
        started_at=1000.0,
        ended_at=1001.0,
        status=RunStatus.PARTIAL,
        events=events,
    )


# ============================================================================
# Model Tests
# ============================================================================

class TestReplayModels:
    """Tests for replay data models."""

    def test_replay_event_creation(self, sample_event):
        assert sample_event.sequence == 0
        assert sample_event.event_id == "evt-001"
        assert sample_event.event_type == "agent.started"
        assert sample_event.integrity == EventIntegrity.VALID

    def test_replay_event_to_dict(self, sample_event):
        d = sample_event.to_dict()
        assert d["sequence"] == 0
        assert d["event_id"] == "evt-001"
        assert d["event_type"] == "agent.started"

    def test_replay_run_creation(self, sample_run):
        assert sample_run.run_id == "run-123"
        assert sample_run.event_count == 6
        assert sample_run.duration == 5.0
        assert sample_run.status == RunStatus.COMPLETE

    def test_replay_run_to_dict(self, sample_run):
        d = sample_run.to_dict()
        assert d["run_id"] == "run-123"
        assert d["event_count"] == 6
        assert d["duration"] == 5.0

    def test_run_status_values(self):
        assert RunStatus.COMPLETE == "complete"
        assert RunStatus.PARTIAL == "partial"
        assert RunStatus.CORRUPTED == "corrupted"
        assert RunStatus.INCONSISTENT == "inconsistent"

    def test_event_integrity_values(self):
        assert EventIntegrity.VALID == "valid"
        assert EventIntegrity.WARNING == "warning"
        assert EventIntegrity.INCONSISTENT == "inconsistent"
        assert EventIntegrity.CORRUPTED == "corrupted"

    def test_timeline_entry_creation(self):
        entry = TimelineEntry(
            sequence=0,
            timestamp=1000.0,
            event_type="agent.started",
            category="agent",
            source="agent",
        )
        assert entry.sequence == 0
        assert entry.event_type == "agent.started"

    def test_execution_node_creation(self):
        node = ExecutionNode(
            node_id="root",
            event_type="run",
            category="run",
            source="agent",
            timestamp=1000.0,
        )
        assert node.node_id == "root"
        assert node.children == []

    def test_security_decision_creation(self):
        decision = SecurityDecision(
            decision_id="sec-001",
            timestamp=1000.0,
            capability="shell.execute",
            risk_level="high",
            decision="allowed",
        )
        assert decision.capability == "shell.execute"
        assert decision.decision == "allowed"

    def test_recovery_action_creation(self):
        action = RecoveryAction(
            action_id="rec-001",
            timestamp=1000.0,
            failure_class="test_failure",
            strategy="retry",
            attempt_number=1,
            budget_before=3,
            budget_after=2,
            success=True,
        )
        assert action.strategy == "retry"
        assert action.success is True

    def test_verification_result_creation(self):
        result = VerificationResult(
            result_id="ver-001",
            timestamp=1000.0,
            criteria_name="tests_pass",
            passed=True,
            confidence=1.0,
        )
        assert result.passed is True

    def test_review_result_creation(self):
        result = ReviewResult(
            result_id="rev-001",
            timestamp=1000.0,
            status="pass",
            findings_count=0,
        )
        assert result.status == "pass"

    def test_state_diff_creation(self):
        diff = StateDiff(
            files_added=["new.py"],
            files_modified=["changed.py"],
            files_deleted=["old.py"],
        )
        assert diff.files_added == ["new.py"]
        assert diff.files_modified == ["changed.py"]
        assert diff.files_deleted == ["old.py"]


# ============================================================================
# Timeline Tests
# ============================================================================

class TestReplayTimeline:
    """Tests for the replay timeline."""

    def test_timeline_sorting(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        events = timeline.events
        # Events should be sorted by sequence
        sequences = [e.sequence for e in events]
        assert sequences == sorted(sequences)

    def test_timeline_all(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        entries = timeline.all()
        assert len(entries) == 6

    def test_timeline_by_category(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        agent_entries = timeline.by_category("agent")
        assert len(agent_entries) == 2  # started + completed

    def test_timeline_by_type(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        started_entries = timeline.by_type("agent.started")
        assert len(started_entries) == 1

    def test_timeline_errors(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        errors = timeline.errors()
        # No errors in sample run
        assert len(errors) == 0

    def test_timeline_security_events(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        security = timeline.security_events()
        assert len(security) == 0

    def test_timeline_capability_events(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        caps = timeline.capability_events()
        assert len(caps) == 2  # started + completed

    def test_timeline_between(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        entries = timeline.between(1001.0, 1003.0)
        assert len(entries) == 3

    def test_timeline_format(self, sample_run):
        timeline = ReplayTimeline(sample_run)
        formatted = timeline.format_timeline()
        assert "agent.started" in formatted
        assert "agent.completed" in formatted


# ============================================================================
# State Reducer Tests
# ============================================================================

class TestStateReducer:
    """Tests for state reconstruction."""

    def test_reduce_simple_run(self, sample_run):
        reducer = StateReducer()
        state = reducer.reduce(sample_run)
        assert state["agent_status"] == "completed"

    def test_reduce_with_initial_state(self):
        run = ReplayRun(
            run_id="test",
            initial_state={"files": {"test.py": "original"}},
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="agent.completed",
                    category="agent",
                    source="agent",
                    run_id="test",
                ),
            ],
        )
        reducer = StateReducer()
        state = reducer.reduce(run)
        assert state["files"]["test.py"] == "original"
        assert state["agent_status"] == "completed"

    def test_reduce_determinism(self, sample_run):
        """Running reduction twice produces same result."""
        reducer1 = StateReducer()
        state1 = reducer1.reduce(sample_run)

        reducer2 = StateReducer()
        state2 = reducer2.reduce(sample_run)

        assert state1 == state2

    def test_reduce_to_event(self, sample_run):
        reducer = StateReducer()
        state = reducer.reduce_to_event(sample_run, 2)
        assert "_last_event_sequence" in state

    def test_reduce_convenience_function(self, sample_run):
        state = reduce_run(sample_run)
        assert state["agent_status"] == "completed"


# ============================================================================
# Execution Tree Tests
# ============================================================================

class TestExecutionTree:
    """Tests for execution tree construction."""

    def test_build_tree(self, sample_run):
        tree = build_execution_tree(sample_run)
        assert tree is not None
        assert tree.node_id == "root"

    def test_build_tree_empty_run(self):
        run = ReplayRun(run_id="empty")
        tree = build_execution_tree(run)
        assert tree is None

    def test_format_tree(self, sample_run):
        tree = build_execution_tree(sample_run)
        formatted = format_execution_tree(tree)
        assert "agent.started" in formatted

    def test_tree_has_children(self, sample_run):
        tree = build_execution_tree(sample_run)
        assert len(tree.children) > 0


# ============================================================================
# Consistency Checker Tests
# ============================================================================

class TestConsistencyChecker:
    """Tests for consistency checking."""

    def test_valid_run(self, sample_run):
        checker = ReplayConsistencyChecker(sample_run)
        issues = checker.check()
        # Sample run should be valid
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_duplicate_sequence_detection(self):
        run = ReplayRun(
            run_id="dup-seq",
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
                    sequence=0,  # Duplicate
                    event_id="evt-002",
                    timestamp=1001.0,
                    event_type="agent.completed",
                    category="agent",
                    source="agent",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("Duplicate sequence" in i.description for i in issues)

    def test_duplicate_event_id_detection(self):
        run = ReplayRun(
            run_id="dup-evt",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-same",
                    timestamp=1000.0,
                    event_type="agent.started",
                    category="agent",
                    source="agent",
                ),
                ReplayEvent(
                    sequence=1,
                    event_id="evt-same",  # Duplicate
                    timestamp=1001.0,
                    event_type="agent.completed",
                    category="agent",
                    source="agent",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("Duplicate event ID" in i.description for i in issues)

    def test_missing_parent_reference(self):
        run = ReplayRun(
            run_id="bad-parent",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="capability.started",
                    category="capability",
                    source="capability_router",
                    parent_id="nonexistent",  # Bad reference
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("unknown parent" in i.description for i in issues)

    def test_capability_end_without_start(self):
        run = ReplayRun(
            run_id="end-no-start",
            events=[
                ReplayEvent(
                    sequence=0,
                    event_id="evt-001",
                    timestamp=1000.0,
                    event_type="capability.completed",
                    category="capability",
                    source="capability_router",
                    capability="read_file",
                ),
            ],
        )
        checker = ReplayConsistencyChecker(run)
        issues = checker.check()
        assert any("ended but never started" in i.description for i in issues)

    def test_partial_run_consistency(self, partial_run):
        checker = ReplayConsistencyChecker(partial_run)
        issues = checker.check()
        # Should not crash on partial runs
        assert isinstance(issues, list)

    def test_consistency_convenience_function(self, sample_run):
        issues = check_consistency(sample_run)
        assert isinstance(issues, list)


# ============================================================================
# Diff Tests
# ============================================================================

class TestReplayDiff:
    """Tests for state diffing."""

    def test_diff_states(self):
        diff = ReplayDiff()
        state1 = {"files": {"a.py": "original", "b.py": "keep"}, "plan": [1, 2]}
        state2 = {"files": {"a.py": "modified", "c.py": "new"}, "plan": [1, 2, 3]}
        result = diff.diff_states(state1, state2)
        assert "a.py" in result.files_modified
        assert "b.py" in result.files_deleted
        assert "c.py" in result.files_added

    def test_diff_empty_states(self):
        diff = ReplayDiff()
        result = diff.diff_states({}, {})
        assert result.files_added == []
        assert result.files_modified == []
        assert result.files_deleted == []

    def test_diff_run_states(self):
        run = ReplayRun(
            run_id="diff-test",
            initial_state={"files": {"test.py": "original"}},
            final_state={"files": {"test.py": "modified"}},
        )
        diff = ReplayDiff()
        result = diff.diff_run_states(run)
        assert "test.py" in result.files_modified

    def test_format_diff(self):
        diff = ReplayDiff()
        state_diff = StateDiff(
            files_added=["new.py"],
            files_modified=["changed.py"],
            files_deleted=["old.py"],
        )
        formatted = diff.format_diff(state_diff)
        assert "new.py" in formatted
        assert "changed.py" in formatted
        assert "old.py" in formatted


# ============================================================================
# Forensic Report Tests
# ============================================================================

class TestForensicReport:
    """Tests for forensic report generation."""

    def test_generate_report(self, sample_run):
        report = ForensicReport(sample_run)
        result = report.generate()
        assert "overview" in result
        assert "execution_summary" in result
        assert "security" in result
        assert "recovery" in result
        assert "verification" in result
        assert "review" in result
        assert "state" in result
        assert "consistency" in result

    def test_report_overview(self, sample_run):
        report = ForensicReport(sample_run)
        result = report.generate()
        overview = result["overview"]
        assert overview["run_id"] == "run-123"
        assert overview["status"] == "complete"
        assert overview["event_count"] == 6

    def test_report_to_json(self, sample_run):
        report = ForensicReport(sample_run)
        json_str = report.to_json()
        assert '"run_id"' in json_str
        assert '"run-123"' in json_str

    def test_report_to_text(self, sample_run):
        report = ForensicReport(sample_run)
        text = report.to_text()
        assert "ARGUS FORENSIC REPORT" in text
        assert "run-123" in text

    def test_generate_forensic_report_convenience(self, sample_run):
        report = generate_forensic_report(sample_run)
        assert isinstance(report, ForensicReport)


# ============================================================================
# Loader Tests
# ============================================================================

class TestReplayLoader:
    """Tests for run loading."""

    def test_loader_creation(self):
        loader = ReplayLoader()
        assert loader is not None

    def test_load_partial_run(self):
        events = [
            {
                "event_id": "evt-001",
                "timestamp": 1000.0,
                "event_type": "agent.started",
                "category": "agent",
                "source": "agent",
            },
            {
                "event_id": "evt-002",
                "timestamp": 1001.0,
                "event_type": "agent.completed",
                "category": "agent",
                "source": "agent",
            },
        ]
        loader = ReplayLoader()
        run = loader.load_partial("test-run", events)
        assert run.run_id == "test-run"
        assert len(run.events) == 2
        assert run.status == RunStatus.PARTIAL

    def test_normalize_event(self):
        loader = ReplayLoader()
        raw = {
            "event_id": "evt-001",
            "timestamp": 1000.0,
            "event_type": "test.event",
            "category": "test",
            "source": "test",
            "payload": {"key": "value"},
        }
        event = loader._normalize_event(raw, sequence=0)
        assert event.event_id == "evt-001"
        assert event.sequence == 0
        assert event.payload == {"key": "value"}


# ============================================================================
# Checkpoint Tests
# ============================================================================

class TestCheckpointManager:
    """Tests for checkpoint management."""

    def test_get_checkpoints(self):
        run = ReplayRun(
            run_id="test",
            checkpoints=[
                ReplayCheckpoint(
                    checkpoint_id="cp-001",
                    sequence=0,
                    timestamp=1000.0,
                    label="start",
                ),
                ReplayCheckpoint(
                    checkpoint_id="cp-002",
                    sequence=1,
                    timestamp=2000.0,
                    label="middle",
                ),
            ],
        )
        manager = CheckpointManager(run)
        checkpoints = manager.get_checkpoints()
        assert len(checkpoints) == 2

    def test_get_checkpoint(self):
        run = ReplayRun(
            run_id="test",
            checkpoints=[
                ReplayCheckpoint(
                    checkpoint_id="cp-001",
                    sequence=0,
                    timestamp=1000.0,
                ),
            ],
        )
        manager = CheckpointManager(run)
        cp = manager.get_checkpoint("cp-001")
        assert cp is not None
        assert cp.checkpoint_id == "cp-001"

    def test_get_checkpoint_at_sequence(self):
        run = ReplayRun(
            run_id="test",
            checkpoints=[
                ReplayCheckpoint(checkpoint_id="cp-001", sequence=0, timestamp=1000.0),
                ReplayCheckpoint(checkpoint_id="cp-002", sequence=5, timestamp=2000.0),
                ReplayCheckpoint(checkpoint_id="cp-003", sequence=10, timestamp=3000.0),
            ],
        )
        manager = CheckpointManager(run)
        cp = manager.get_checkpoint_at_sequence(7)
        assert cp is not None
        assert cp.checkpoint_id == "cp-002"

    def test_compare_checkpoints(self):
        run = ReplayRun(
            run_id="test",
            checkpoints=[
                ReplayCheckpoint(
                    checkpoint_id="cp-001",
                    sequence=0,
                    timestamp=1000.0,
                    state={"x": 1},
                ),
                ReplayCheckpoint(
                    checkpoint_id="cp-002",
                    sequence=1,
                    timestamp=2000.0,
                    state={"x": 2, "y": 3},
                ),
            ],
        )
        manager = CheckpointManager(run)
        comparison = manager.compare_checkpoints("cp-001", "cp-002")
        assert "differences" in comparison

    def test_restore_for_analysis(self):
        run = ReplayRun(
            run_id="test",
            checkpoints=[
                ReplayCheckpoint(
                    checkpoint_id="cp-001",
                    sequence=0,
                    timestamp=1000.0,
                    state={"files": {"test.py": "content"}},
                ),
            ],
        )
        manager = CheckpointManager(run)
        state = manager.restore_for_analysis("cp-001")
        assert state is not None
        assert state["files"]["test.py"] == "content"


# ============================================================================
# Replay Engine Tests
# ============================================================================

class TestReplayEngine:
    """Tests for the replay engine."""

    def test_engine_creation(self):
        engine = ReplayEngine()
        assert engine is not None

    def test_load_and_replay(self, sample_run):
        engine = ReplayEngine()
        engine._runs[sample_run.run_id] = sample_run

        result = engine.replay(sample_run.run_id)
        assert result is not None
        assert result.run_id == sample_run.run_id

    def test_reconstruct_state(self, sample_run):
        engine = ReplayEngine()
        engine._runs[sample_run.run_id] = sample_run

        state = engine.reconstruct_state(sample_run.run_id)
        assert state is not None
        assert state["agent_status"] == "completed"

    def test_get_timeline(self, sample_run):
        engine = ReplayEngine()
        engine._runs[sample_run.run_id] = sample_run

        timeline = engine.get_timeline(sample_run.run_id)
        assert timeline is not None
        assert len(timeline.all()) == 6

    def test_replay_nonexistent_run(self):
        engine = ReplayEngine()
        result = engine.replay("nonexistent")
        assert result is None


# ============================================================================
# Determinism Tests
# ============================================================================

class TestDeterminism:
    """Tests for replay determinism."""

    def test_timeline_determinism(self, sample_run):
        """Same run produces same timeline twice."""
        timeline1 = ReplayTimeline(sample_run)
        entries1 = [(e.sequence, e.event_type) for e in timeline1.all()]

        timeline2 = ReplayTimeline(sample_run)
        entries2 = [(e.sequence, e.event_type) for e in timeline2.all()]

        assert entries1 == entries2

    def test_reducer_determinism(self, sample_run):
        """Same run produces same state twice."""
        reducer1 = StateReducer()
        state1 = reducer1.reduce(sample_run)

        reducer2 = StateReducer()
        state2 = reducer2.reduce(sample_run)

        assert state1 == state2

    def test_consistency_determinism(self, sample_run):
        """Same run produces same consistency issues twice."""
        checker1 = ReplayConsistencyChecker(sample_run)
        issues1 = checker1.check()

        checker2 = ReplayConsistencyChecker(sample_run)
        issues2 = checker2.check()

        assert len(issues1) == len(issues2)

    def test_tree_determinism(self, sample_run):
        """Same run produces same tree twice."""
        tree1 = build_execution_tree(sample_run)
        tree2 = build_execution_tree(sample_run)

        assert tree1.node_id == tree2.node_id
        assert len(tree1.children) == len(tree2.children)
