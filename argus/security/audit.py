"""Audit trail for ARGUS security events."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEventType(str, Enum):
    """Types of audit events."""
    PERMISSION_REQUESTED = "permission_requested"
    PERMISSION_EVALUATED = "permission_evaluated"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    SECRET_ACCESSED = "secret_accessed"
    POLICY_VIOLATION = "policy_violation"
    INJECTION_DETECTED = "injection_detected"
    RISK_ASSESSED = "risk_assessed"
    SANDBOX_VIOLATION = "sandbox_violation"


@dataclass
class AuditEvent:
    """A security audit event."""
    event_type: AuditEventType
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    capability_id: str = ""
    run_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = ""
    decision: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "capability_id": self.capability_id,
            "run_id": self.run_id,
            "details": self.details,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
        }


class AuditTrail:
    """Records security audit events."""

    def __init__(self, max_events: int = 1000):
        self._events: List[AuditEvent] = []
        self._max_events = max_events

    def record(
        self,
        event_type: AuditEventType,
        capability_id: str = "",
        run_id: str = "",
        details: Dict[str, Any] = None,
        risk_level: str = "",
        decision: str = "",
        reason: str = "",
    ) -> AuditEvent:
        """Record an audit event."""
        event = AuditEvent(
            event_type=event_type,
            capability_id=capability_id,
            run_id=run_id,
            details=details or {},
            risk_level=risk_level,
            decision=decision,
            reason=reason,
        )
        self._events.append(event)

        # Trim if needed
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        return event

    def get_events(
        self,
        event_type: Optional[AuditEventType] = None,
        capability_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit events."""
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if capability_id:
            events = [e for e in events if e.capability_id == capability_id]
        if run_id:
            events = [e for e in events if e.run_id == run_id]

        return events[-limit:]

    def get_violations(self, run_id: Optional[str] = None) -> List[AuditEvent]:
        """Get policy violation events."""
        violations = [
            AuditEventType.POLICY_VIOLATION,
            AuditEventType.INJECTION_DETECTED,
            AuditEventType.SANDBOX_VIOLATION,
        ]
        events = [e for e in self._events if e.event_type in violations]
        if run_id:
            events = [e for e in events if e.run_id == run_id]
        return events

    def count_events(self, event_type: AuditEventType) -> int:
        """Count events of a type."""
        return sum(1 for e in self._events if e.event_type == event_type)

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dicts."""
        return [e.to_dict() for e in self._events]

    def __len__(self) -> int:
        return len(self._events)