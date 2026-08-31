"""Backpressure handling for capacity management."""

import threading
import time
from typing import Optional

from argus.performance.models import BackpressureAction
from argus.performance.resources import ResourceController, ResourceType


class BackpressureError(Exception):
    """Backpressure error."""
    pass


class BackpressureController:
    """Controls backpressure when capacity is reached."""

    def __init__(
        self,
        resource_controller: Optional[ResourceController] = None,
        default_action: BackpressureAction = BackpressureAction.QUEUE,
        max_wait_seconds: float = 30.0,
    ):
        self._resource_controller = resource_controller
        self._default_action = default_action
        self._max_wait_seconds = max_wait_seconds
        self._lock = threading.Lock()
        self._wait_count = 0
        self._reject_count = 0
        self._throttle_count = 0

    def check_capacity(
        self,
        resource_type: ResourceType,
        action: Optional[BackpressureAction] = None,
    ) -> BackpressureAction:
        """
        Check capacity and determine backpressure action.

        Returns the action to take.
        """
        action = action or self._default_action

        if self._resource_controller is None:
            return BackpressureAction.ACCEPT

        if self._resource_controller.check_available(resource_type):
            return BackpressureAction.ACCEPT

        # Resource is exhausted, apply backpressure
        if action == BackpressureAction.QUEUE:
            with self._lock:
                self._wait_count += 1
            return BackpressureAction.QUEUE
        elif action == BackpressureAction.THROTTLE:
            with self._lock:
                self._throttle_count += 1
            return BackpressureAction.THROTTLE
        elif action == BackpressureAction.REJECT:
            with self._lock:
                self._reject_count += 1
            return BackpressureAction.REJECT
        elif action == BackpressureAction.CANCEL:
            return BackpressureAction.CANCEL

        return action

    def wait_for_capacity(
        self,
        resource_type: ResourceType,
        timeout: Optional[float] = None,
    ) -> bool:
        """Wait for capacity to become available."""
        timeout = timeout or self._max_wait_seconds
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            if self._resource_controller and self._resource_controller.check_available(resource_type):
                return True
            time.sleep(0.01)

        return False

    def get_stats(self) -> dict:
        """Get backpressure statistics."""
        with self._lock:
            return {
                "wait_count": self._wait_count,
                "reject_count": self._reject_count,
                "throttle_count": self._throttle_count,
            }

    def reset_stats(self) -> None:
        """Reset backpressure statistics."""
        with self._lock:
            self._wait_count = 0
            self._reject_count = 0
            self._throttle_count = 0
