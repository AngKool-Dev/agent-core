"""UX state management for ARGUS product layer."""

import threading
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from argus.ux.models import (
    EventSeverity,
    ExecutionPlan,
    LifecyclePhase,
    PlanStep,
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


class UXState:
    """Thread-safe UX state management."""

    def __init__(self, config: Optional[UXConfiguration] = None):
        self._config = config or UXConfiguration()
        self._lock = threading.Lock()
        self._current_phase: LifecyclePhase = LifecyclePhase.IDLE
        self._plan: Optional[ExecutionPlan] = None
        self._events: Deque[UIEvent] = deque(maxlen=self._config.max_event_history)
        self._provider_status: Optional[ProviderStatus] = None
        self._security_status = SecurityStatus()
        self._performance_status = PerformanceStatus()
        self._verification_status = VerificationStatus()
        self._recovery_status = RecoveryStatus()
        self._review_status = ReviewStatus()
        self._error_message: Optional[str] = None
        self._status_message: str = ""

    @property
    def config(self) -> UXConfiguration:
        """Get UX configuration."""
        return self._config

    @property
    def current_phase(self) -> LifecyclePhase:
        """Get current lifecycle phase."""
        with self._lock:
            return self._current_phase

    @current_phase.setter
    def current_phase(self, phase: LifecyclePhase) -> None:
        """Set current lifecycle phase."""
        with self._lock:
            self._current_phase = phase

    @property
    def plan(self) -> Optional[ExecutionPlan]:
        """Get current execution plan."""
        with self._lock:
            return self._plan

    @plan.setter
    def plan(self, plan: Optional[ExecutionPlan]) -> None:
        """Set current execution plan."""
        with self._lock:
            self._plan = plan

    @property
    def events(self) -> List[UIEvent]:
        """Get all events."""
        with self._lock:
            return list(self._events)

    def add_event(self, event: UIEvent) -> None:
        """Add an event to the history."""
        with self._lock:
            self._events.append(event)

    def clear_events(self) -> None:
        """Clear all events."""
        with self._lock:
            self._events.clear()

    @property
    def provider_status(self) -> Optional[ProviderStatus]:
        """Get provider status."""
        with self._lock:
            return self._provider_status

    @provider_status.setter
    def provider_status(self, status: Optional[ProviderStatus]) -> None:
        """Set provider status."""
        with self._lock:
            self._provider_status = status

    @property
    def security_status(self) -> SecurityStatus:
        """Get security status."""
        with self._lock:
            return self._security_status

    @security_status.setter
    def security_status(self, status: SecurityStatus) -> None:
        """Set security status."""
        with self._lock:
            self._security_status = status

    @property
    def performance_status(self) -> PerformanceStatus:
        """Get performance status."""
        with self._lock:
            return self._performance_status

    @performance_status.setter
    def performance_status(self, status: PerformanceStatus) -> None:
        """Set performance status."""
        with self._lock:
            self._performance_status = status

    @property
    def verification_status(self) -> VerificationStatus:
        """Get verification status."""
        with self._lock:
            return self._verification_status

    @verification_status.setter
    def verification_status(self, status: VerificationStatus) -> None:
        """Set verification status."""
        with self._lock:
            self._verification_status = status

    @property
    def recovery_status(self) -> RecoveryStatus:
        """Get recovery status."""
        with self._lock:
            return self._recovery_status

    @recovery_status.setter
    def recovery_status(self, status: RecoveryStatus) -> None:
        """Set recovery status."""
        with self._lock:
            self._recovery_status = status

    @property
    def review_status(self) -> ReviewStatus:
        """Get review status."""
        with self._lock:
            return self._review_status

    @review_status.setter
    def review_status(self, status: ReviewStatus) -> None:
        """Set review status."""
        with self._lock:
            self._review_status = status

    @property
    def error_message(self) -> Optional[str]:
        """Get current error message."""
        with self._lock:
            return self._error_message

    @error_message.setter
    def error_message(self, message: Optional[str]) -> None:
        """Set current error message."""
        with self._lock:
            self._error_message = message

    def clear_error(self) -> None:
        """Clear the error message."""
        with self._lock:
            self._error_message = None

    @property
    def status_message(self) -> str:
        """Get current status message."""
        with self._lock:
            return self._status_message

    @status_message.setter
    def status_message(self, message: str) -> None:
        """Set current status message."""
        with self._lock:
            self._status_message = message
