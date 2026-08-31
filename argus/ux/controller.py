"""UX controller for coordinating UI components."""

import threading
from typing import Callable, List, Optional

from argus.ux.events import UXEventSubscriber
from argus.ux.formatting import UXFormatter
from argus.ux.models import (
    EventSeverity,
    ExecutionPlan,
    LifecyclePhase,
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
from argus.ux.state import UXState
from argus.ux.themes import ThemeManager, UXTheme


class UXController:
    """Main controller for UX components."""

    def __init__(self, config: Optional[UXConfiguration] = None):
        self._config = config or UXConfiguration()
        self._state = UXState(self._config)
        self._formatter = UXFormatter(
            use_unicode=self._config.unicode,
            use_color=self._config.color,
        )
        self._theme_manager = ThemeManager()
        self._event_subscriber = UXEventSubscriber()
        self._render_callbacks: List[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._active = False

    @property
    def state(self) -> UXState:
        """Get UX state."""
        return self._state

    @property
    def formatter(self) -> UXFormatter:
        """Get UX formatter."""
        return self._formatter

    @property
    def theme_manager(self) -> ThemeManager:
        """Get theme manager."""
        return self._theme_manager

    @property
    def config(self) -> UXConfiguration:
        """Get UX configuration."""
        return self._config

    def start(self) -> None:
        """Start the UX controller."""
        with self._lock:
            if self._active:
                return
            self._event_subscriber.add_handler(self._on_ui_event)
            self._event_subscriber.start()
            self._active = True

    def stop(self) -> None:
        """Stop the UX controller."""
        with self._lock:
            if not self._active:
                return
            self._event_subscriber.stop()
            self._event_subscriber.remove_handler(self._on_ui_event)
            self._active = False

    def register_render_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when state changes."""
        with self._lock:
            self._render_callbacks.append(callback)

    def unregister_render_callback(self, callback: Callable[[], None]) -> None:
        """Unregister a render callback."""
        with self._lock:
            self._render_callbacks.remove(callback)

    def _on_ui_event(self, event: UIEvent) -> None:
        """Handle a UI event."""
        self._state.add_event(event)
        self._notify_render_callbacks()

    def _notify_render_callbacks(self) -> None:
        """Notify all render callbacks."""
        with self._lock:
            callbacks = list(self._render_callbacks)
        for callback in callbacks:
            try:
                callback()
            except Exception:
                pass  # Don't let callback errors break the controller

    def update_phase(self, phase: LifecyclePhase) -> None:
        """Update the current lifecycle phase."""
        self._state.current_phase = phase
        self._notify_render_callbacks()

    def update_plan(self, plan: ExecutionPlan) -> None:
        """Update the execution plan."""
        self._state.plan = plan
        self._notify_render_callbacks()

    def update_provider_status(self, status: ProviderStatus) -> None:
        """Update provider status."""
        self._state.provider_status = status
        self._notify_render_callbacks()

    def update_security_status(self, status: SecurityStatus) -> None:
        """Update security status."""
        self._state.security_status = status
        self._notify_render_callbacks()

    def update_performance_status(self, status: PerformanceStatus) -> None:
        """Update performance status."""
        self._state.performance_status = status
        self._notify_render_callbacks()

    def update_verification_status(self, status: VerificationStatus) -> None:
        """Update verification status."""
        self._state.verification_status = status
        self._notify_render_callbacks()

    def update_recovery_status(self, status: RecoveryStatus) -> None:
        """Update recovery status."""
        self._state.recovery_status = status
        self._notify_render_callbacks()

    def update_review_status(self, status: ReviewStatus) -> None:
        """Update review status."""
        self._state.review_status = status
        self._notify_render_callbacks()

    def set_error(self, message: str) -> None:
        """Set an error message."""
        self._state.error_message = message
        self._notify_render_callbacks()

    def clear_error(self) -> None:
        """Clear the error message."""
        self._state.error_message = None
        self._notify_render_callbacks()

    def set_status(self, message: str) -> None:
        """Set a status message."""
        self._state.status_message = message
        self._notify_render_callbacks()

    @property
    def is_active(self) -> bool:
        """Check if controller is active."""
        return self._active
