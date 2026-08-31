"""Resilience reporting."""

from typing import Any, Dict, List, Optional


class ResilienceReporter:
    """Generates resilience reports."""

    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self._events.append({
            "type": event_type,
            "data": data,
        })

    def get_events(self) -> List[Dict[str, Any]]:
        return self._events.copy()

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self._events if e["type"] == event_type]

    def get_events_by_provider(self, provider: str) -> List[Dict[str, Any]]:
        return [
            e for e in self._events
            if e["data"].get("provider") == provider
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_events": len(self._events),
            "event_types": {
                t: len(self.get_events_by_type(t))
                for t in set(e["type"] for e in self._events)
            },
        }

    def clear(self) -> None:
        self._events.clear()

    def generate_report(self) -> Dict[str, Any]:
        return {
            "events": self._events,
            "summary": self.get_summary(),
        }

    def export(self) -> Dict[str, Any]:
        return self.generate_report()
