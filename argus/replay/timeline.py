"""ARGUS Replay timeline with deterministic ordering."""

import time
from typing import Any, Callable, Dict, List, Optional, Set

from argus.replay.models import (
    ReplayEvent,
    ReplayRun,
    TimelineEntry,
)


class ReplayTimeline:
    """Provides deterministic timeline views of a replay run."""

    def __init__(self, run: ReplayRun):
        self._run = run
        self._events = self._sort_events(run.events)

    @property
    def events(self) -> List[ReplayEvent]:
        """Get sorted events."""
        return self._events

    def all(self) -> List[TimelineEntry]:
        """Get all events as timeline entries."""
        return [self._to_entry(e) for e in self._events]

    def between(self, start: float, end: float) -> List[TimelineEntry]:
        """Get events between two timestamps."""
        return [
            self._to_entry(e) for e in self._events
            if start <= e.timestamp <= end
        ]

    def by_category(self, category: str) -> List[TimelineEntry]:
        """Get events filtered by category."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == category
        ]

    def by_type(self, event_type: str) -> List[TimelineEntry]:
        """Get events filtered by type."""
        return [
            self._to_entry(e) for e in self._events
            if e.event_type == event_type
        ]

    def by_source(self, source: str) -> List[TimelineEntry]:
        """Get events filtered by source."""
        return [
            self._to_entry(e) for e in self._events
            if e.source == source
        ]

    def errors(self) -> List[TimelineEntry]:
        """Get error events."""
        return [
            self._to_entry(e) for e in self._events
            if e.status == "failed" or "error" in e.event_type
        ]

    def security_events(self) -> List[TimelineEntry]:
        """Get security-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "security"
        ]

    def capability_events(self) -> List[TimelineEntry]:
        """Get capability-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "capability"
        ]

    def recovery_events(self) -> List[TimelineEntry]:
        """Get recovery-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "recovery"
        ]

    def verification_events(self) -> List[TimelineEntry]:
        """Get verification-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "verification"
        ]

    def review_events(self) -> List[TimelineEntry]:
        """Get review-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "review" or "review" in e.event_type
        ]

    def model_events(self) -> List[TimelineEntry]:
        """Get model-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "model"
        ]

    def execution_events(self) -> List[TimelineEntry]:
        """Get execution-related events."""
        return [
            self._to_entry(e) for e in self._events
            if e.category == "execution"
        ]

    def _sort_events(self, events: List[ReplayEvent]) -> List[ReplayEvent]:
        """Sort events deterministically.

        Primary: sequence number
        Fallback: timestamp
        Final tie-breaker: event_id
        """
        return sorted(events, key=lambda e: (e.sequence, e.timestamp, e.event_id))

    def _to_entry(self, event: ReplayEvent) -> TimelineEntry:
        """Convert a ReplayEvent to a TimelineEntry."""
        return TimelineEntry(
            sequence=event.sequence,
            timestamp=event.timestamp,
            event_type=event.event_type,
            category=event.category,
            source=event.source,
            status=event.status,
            capability=event.capability,
            duration=event.duration,
            description=self._describe_event(event),
        )

    def _describe_event(self, event: ReplayEvent) -> str:
        """Generate a human-readable description for an event."""
        parts = [event.event_type]

        if event.capability:
            parts.append(f"capability={event.capability}")

        if event.status:
            parts.append(f"status={event.status}")

        if event.duration:
            parts.append(f"duration={event.duration:.2f}s")

        if event.source:
            parts.append(f"source={event.source}")

        return " | ".join(parts)

    def format_timeline(self, entries: Optional[List[TimelineEntry]] = None) -> str:
        """Format timeline entries as a string."""
        if entries is None:
            entries = self.all()

        lines = []
        for entry in entries:
            timestamp = self._format_timestamp(entry.timestamp)
            lines.append(
                f"{timestamp} [{entry.sequence:04d}] "
                f"{entry.event_type} ({entry.category})"
            )
            if entry.status:
                lines.append(f"  status: {entry.status}")
            if entry.capability:
                lines.append(f"  capability: {entry.capability}")
            if entry.duration:
                lines.append(f"  duration: {entry.duration:.2f}s")

        return "\n".join(lines)

    def _format_timestamp(self, timestamp: float) -> str:
        """Format a timestamp for display."""
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%H:%M:%S.%f")[:-3]
