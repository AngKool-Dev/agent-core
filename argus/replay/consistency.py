"""ARGUS Replay consistency checker - detects contradictions in runs."""

import logging
from typing import Any, Dict, List, Optional, Set

from argus.replay.models import (
    ConsistencyIssue,
    ReplayEvent,
    ReplayRun,
    RunStatus,
)

logger = logging.getLogger(__name__)


class ReplayConsistencyChecker:
    """Checks for contradictions and inconsistencies in replay runs."""

    def __init__(self, run: ReplayRun):
        self._run = run
        self._issues: List[ConsistencyIssue] = []

    def check(self) -> List[ConsistencyIssue]:
        """Run all consistency checks.

        Returns:
            List of consistency issues found
        """
        self._issues = []

        self._check_sequence_integrity()
        self._check_event_uniqueness()
        self._check_parent_references()
        self._check_lifecycle_completeness()
        self._check_impossible_transitions()
        self._check_cross_run_contamination()
        self._check_timestamp_ordering()

        return self._issues

    def _check_sequence_integrity(self):
        """Check for missing or duplicate sequence numbers."""
        sequences = [e.sequence for e in self._run.events]
        if not sequences:
            return

        # Check for duplicates
        seen = set()
        for seq in sequences:
            if seq in seen:
                self._issues.append(ConsistencyIssue(
                    issue_id=f"dup_seq_{seq}",
                    severity="error",
                    description=f"Duplicate sequence number: {seq}",
                    event_sequence=seq,
                ))
            seen.add(seq)

        # Check for gaps
        expected = set(range(min(sequences), max(sequences) + 1))
        missing = expected - seen
        for seq in sorted(missing):
            self._issues.append(ConsistencyIssue(
                issue_id=f"missing_seq_{seq}",
                severity="warning",
                description=f"Missing sequence number: {seq}",
                event_sequence=seq,
            ))

    def _check_event_uniqueness(self):
        """Check for duplicate event IDs."""
        event_ids = [e.event_id for e in self._run.events]
        seen = set()
        for event_id in event_ids:
            if event_id in seen:
                self._issues.append(ConsistencyIssue(
                    issue_id=f"dup_evt_{event_id}",
                    severity="error",
                    description=f"Duplicate event ID: {event_id}",
                    related_events=[event_id],
                ))
            seen.add(event_id)

    def _check_parent_references(self):
        """Check that parent references point to valid events."""
        event_ids = {e.event_id for e in self._run.events}

        for event in self._run.events:
            if event.parent_id and event.parent_id not in event_ids:
                self._issues.append(ConsistencyIssue(
                    issue_id=f"bad_parent_{event.event_id}",
                    severity="warning",
                    description=f"Event {event.event_id} references unknown parent: {event.parent_id}",
                    event_sequence=event.sequence,
                    related_events=[event.event_id, event.parent_id],
                ))

    def _check_lifecycle_completeness(self):
        """Check that lifecycle events are complete."""
        event_types = {e.event_type for e in self._run.events}

        # Check for completion without start
        capability_starts = set()
        capability_ends = set()
        execution_starts = set()
        execution_ends = set()

        for event in self._run.events:
            if event.event_type == "capability.started":
                capability_starts.add(event.capability)
            elif event.event_type in ("capability.completed", "capability.failed"):
                capability_ends.add(event.capability)
            elif event.event_type == "execution.started":
                execution_starts.add(event.sequence)
            elif event.event_type in ("execution.completed", "execution.failed"):
                execution_ends.add(event.sequence)

        # Capabilities that ended but didn't start
        for cap in capability_ends - capability_starts:
            self._issues.append(ConsistencyIssue(
                issue_id=f"cap_end_no_start_{cap}",
                severity="warning",
                description=f"Capability {cap} ended but never started",
                related_events=[cap],
            ))

        # Check for agent completion without required review
        if "agent.completed" in event_types:
            # Review should have happened
            if "review.completed" not in event_types and "verification.completed" not in event_types:
                self._issues.append(ConsistencyIssue(
                    issue_id="no_review_on_complete",
                    severity="warning",
                    description="Agent completed without review or verification",
                    related_events=["agent.completed"],
                ))

    def _check_impossible_transitions(self):
        """Check for impossible state transitions."""
        # Track state per capability
        capability_states: Dict[str, str] = {}

        for event in self._run.events:
            cap = event.capability
            if not cap:
                continue

            current = capability_states.get(cap, "none")

            if event.event_type == "capability.started":
                if current in ("started", "completed"):
                    self._issues.append(ConsistencyIssue(
                        issue_id=f"impossible_start_{cap}_{event.sequence}",
                        severity="error",
                        description=f"Capability {cap} started while in state: {current}",
                        event_sequence=event.sequence,
                    ))
                capability_states[cap] = "started"

            elif event.event_type in ("capability.completed", "capability.failed"):
                if current not in ("started",):
                    self._issues.append(ConsistencyIssue(
                        issue_id=f"impossible_end_{cap}_{event.sequence}",
                        severity="error",
                        description=f"Capability {cap} ended while in state: {current}",
                        event_sequence=event.sequence,
                    ))
                capability_states[cap] = "completed"

        # Check security denied followed by execution completed
        security_denied: Set[str] = set()
        for event in self._run.events:
            if event.event_type == "security.denied":
                security_denied.add(event.capability)
            elif event.event_type == "execution.completed":
                if event.capability in security_denied:
                    # Check if there was an approval after the denial
                    has_approval = any(
                        e.event_type in ("security.approved", "security.allowed")
                        and e.capability == event.capability
                        and e.sequence > next(
                            seq for seq in [ev.sequence for ev in self._run.events if ev.event_type == "security.denied" and ev.capability == event.capability]
                        )
                        for e in self._run.events
                    )
                    if not has_approval:
                        self._issues.append(ConsistencyIssue(
                            issue_id=f"exec_after_deny_{event.capability}",
                            severity="error",
                            description=f"Execution completed for {event.capability} after security denial without approval",
                            event_sequence=event.sequence,
                        ))

    def _check_cross_run_contamination(self):
        """Check for events from other runs."""
        run_ids: Set[str] = set()
        for event in self._run.events:
            if event.run_id:
                run_ids.add(event.run_id)

        # Remove the current run's ID
        run_ids.discard(self._run.run_id)

        if run_ids:
            self._issues.append(ConsistencyIssue(
                issue_id="cross_run_contamination",
                severity="error",
                description=f"Events from other runs found: {run_ids}",
                related_events=list(run_ids),
            ))

    def _check_timestamp_ordering(self):
        """Check that timestamps are monotonically increasing."""
        prev_timestamp = 0.0
        for event in self._run.events:
            if event.timestamp < prev_timestamp:
                self._issues.append(ConsistencyIssue(
                    issue_id=f"timestamp_order_{event.sequence}",
                    severity="warning",
                    description=f"Timestamp decreased at sequence {event.sequence}: {event.timestamp} < {prev_timestamp}",
                    event_sequence=event.sequence,
                ))
            prev_timestamp = event.timestamp


def check_consistency(run: ReplayRun) -> List[ConsistencyIssue]:
    """Convenience function to check consistency of a run."""
    checker = ReplayConsistencyChecker(run)
    return checker.check()
