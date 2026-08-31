"""ARGUS Replay loader - gathers data from existing persistence layers."""

import logging
from typing import Any, Dict, List, Optional

from argus.replay.models import (
    EventIntegrity,
    ReplayCheckpoint,
    ReplayEvent,
    ReplayRun,
    ReplaySnapshot,
    RunStatus,
    SecurityDecision,
    RecoveryAction,
    VerificationResult,
    ReviewResult,
)

logger = logging.getLogger(__name__)


class ReplayLoadError(Exception):
    """Error loading replay data."""
    pass


class ReplayLoader:
    """Loads replay data from existing persistence layers.

    Gathers:
    - EventBus/Event storage
    - StateStore
    - SnapshotManager
    - AuditTrail
    """

    def __init__(self):
        self._event_bus = None
        self._state_store = None
        self._snapshot_manager = None
        self._audit_trail = None
        self._correlation_tracker = None

    def load(self, run_id: str) -> ReplayRun:
        """Load a complete replay run.

        Args:
            run_id: The run ID to load

        Returns:
            ReplayRun with all available data
        """
        run = ReplayRun(run_id=run_id)

        # Load events
        events = self._load_events(run_id)
        run.events = events

        # Load snapshots
        snapshots = self._load_snapshots(run_id)
        run.snapshots = snapshots

        # Load state
        state = self._load_state(run_id)
        if state:
            run.final_state = state

        # Load security decisions
        security_decisions = self._load_security_decisions(run_id)
        run.security_decisions = security_decisions

        # Load checkpoints from snapshots
        run.checkpoints = self._build_checkpoints(snapshots)

        # Determine run status
        run.status = self._determine_status(run)

        # Set timing from events
        if events:
            run.started_at = events[0].timestamp
            run.ended_at = events[-1].timestamp

        # Extract session_id and task from events
        for event in events:
            if not run.session_id and event.session_id:
                run.session_id = event.session_id
            if event.event_type == "task.received" and event.payload:
                run.task = event.payload.get("task", "")

        return run

    def load_partial(self, run_id: str, events: List[Dict]) -> ReplayRun:
        """Load a partial run from provided events.

        Args:
            run_id: The run ID
            events: List of event dictionaries

        Returns:
            ReplayRun with available data
        """
        run = ReplayRun(run_id=run_id, status=RunStatus.PARTIAL)

        # Convert raw events to ReplayEvents
        for i, event_data in enumerate(events):
            event = self._normalize_event(event_data, sequence=i)
            run.events.append(event)

        # Set timing
        if run.events:
            run.started_at = run.events[0].timestamp
            run.ended_at = run.events[-1].timestamp

        return run

    def _load_events(self, run_id: str) -> List[ReplayEvent]:
        """Load events for a run."""
        events = []

        try:
            from argus.events import get_event_bus, get_correlation_tracker
            self._event_bus = get_event_bus()
            self._correlation_tracker = get_correlation_tracker()

            # Get events from correlation tracker
            raw_events = self._correlation_tracker.get_run_events(run_id)

            for i, event in enumerate(raw_events):
                replay_event = ReplayEvent(
                    sequence=i,
                    event_id=event.event_id,
                    timestamp=event.timestamp,
                    event_type=event.event_type.value,
                    category=event.category,
                    source=event.source.value,
                    run_id=event.run_id,
                    session_id=event.session_id,
                    operation_id=event.operation_id,
                    attempt_id=event.attempt_id,
                    parent_id=event.parent_event_id,
                    payload=dict(event.payload),
                    status=event.status.value if event.status else None,
                    capability=event.capability,
                    duration=event.duration,
                    metadata=dict(event.metadata),
                )
                events.append(replay_event)

        except Exception as e:
            logger.warning(f"Could not load events for run {run_id}: {e}")

        return events

    def _load_snapshots(self, run_id: str) -> List[ReplaySnapshot]:
        """Load snapshots for a run."""
        snapshots = []

        try:
            from argus.state import SnapshotManager
            self._snapshot_manager = SnapshotManager()

            raw_snapshots = self._snapshot_manager.get_snapshots(run_id)

            for snap in raw_snapshots:
                snapshot = ReplaySnapshot(
                    snapshot_id=f"snap-{snap.timestamp}",
                    run_id=snap.run_id,
                    timestamp=snap.timestamp,
                    state=dict(snap.state),
                    label=snap.label,
                )
                snapshots.append(snapshot)

        except Exception as e:
            logger.warning(f"Could not load snapshots for run {run_id}: {e}")

        return snapshots

    def _load_state(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load final state for a run."""
        try:
            from argus.state import StateStore
            self._state_store = StateStore()
            state = self._state_store.load_state(run_id)
            if state:
                return state.to_dict()
        except Exception as e:
            logger.warning(f"Could not load state for run {run_id}: {e}")
        return None

    def _load_security_decisions(self, run_id: str) -> List[SecurityDecision]:
        """Load security decisions from audit trail."""
        decisions = []

        try:
            from argus.security import AuditTrail
            self._audit_trail = AuditTrail()

            # Get audit events for this run
            audit_events = self._audit_trail.get_events(run_id=run_id)

            for audit_event in audit_events:
                decision = SecurityDecision(
                    decision_id=f"sec-{audit_event.timestamp}",
                    timestamp=audit_event.timestamp,
                    capability=audit_event.capability_id or "",
                    risk_level=audit_event.risk_level or "",
                    decision=audit_event.decision or "",
                    reason=audit_event.reason or "",
                    source=audit_event.source or "",
                    run_id=run_id,
                )
                decisions.append(decision)

        except Exception as e:
            logger.warning(f"Could not load security decisions for run {run_id}: {e}")

        return decisions

    def _build_checkpoints(self, snapshots: List[ReplaySnapshot]) -> List[ReplayCheckpoint]:
        """Build checkpoints from snapshots."""
        checkpoints = []

        for i, snapshot in enumerate(snapshots):
            checkpoint = ReplayCheckpoint(
                checkpoint_id=snapshot.snapshot_id,
                sequence=i,
                timestamp=snapshot.timestamp,
                state=snapshot.state,
                label=snapshot.label,
            )
            checkpoints.append(checkpoint)

        return checkpoints

    def _normalize_event(self, event_data: Dict[str, Any], sequence: int) -> ReplayEvent:
        """Normalize a raw event dictionary to a ReplayEvent."""
        return ReplayEvent(
            sequence=sequence,
            event_id=event_data.get("event_id", f"evt-{sequence}"),
            timestamp=event_data.get("timestamp", 0.0),
            event_type=event_data.get("event_type", "unknown"),
            category=event_data.get("category", "system"),
            source=event_data.get("source", "unknown"),
            run_id=event_data.get("run_id", ""),
            session_id=event_data.get("session_id", ""),
            operation_id=event_data.get("operation_id"),
            attempt_id=event_data.get("attempt_id"),
            parent_id=event_data.get("parent_id"),
            payload=event_data.get("payload", {}),
            status=event_data.get("status"),
            capability=event_data.get("capability"),
            duration=event_data.get("duration"),
            metadata=event_data.get("metadata", {}),
        )

    def _determine_status(self, run: ReplayRun) -> RunStatus:
        """Determine the status of a run."""
        if not run.events:
            return RunStatus.PARTIAL

        event_types = [e.event_type for e in run.events]

        # Check for completion
        has_start = "agent.started" in event_types
        has_end = "agent.completed" in event_types or "agent.failed" in event_types

        if has_start and has_end:
            return RunStatus.COMPLETE
        elif has_start:
            return RunStatus.PARTIAL
        else:
            return RunStatus.CORRUPTED


def load_run(run_id: str) -> ReplayRun:
    """Convenience function to load a replay run."""
    loader = ReplayLoader()
    return loader.load(run_id)


def load_partial_run(run_id: str, events: List[Dict]) -> ReplayRun:
    """Convenience function to load a partial run."""
    loader = ReplayLoader()
    return loader.load_partial(run_id, events)
