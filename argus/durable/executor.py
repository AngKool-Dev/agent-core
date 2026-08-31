"""ARGUS Durable Executor.

Wraps capability execution with durable journaling and crash safety.
"""

import logging
import os
import signal
import sys
from typing import Any, Callable, Dict, List, Optional

from argus.durable.journal import ExecutionJournal
from argus.durable.models import (
    CrashPoint,
    OperationRecord,
    OperationStatus,
    OperationType,
)

logger = logging.getLogger(__name__)


class DurableExecutor:
    """Executes operations with durable journaling.

    Wraps capability execution to ensure:
    - Operations are journaled before execution
    - Crash points can be injected for testing
    - Operations are marked complete/failed after execution
    """

    def __init__(
        self,
        journal: ExecutionJournal = None,
        crash_points: List[CrashPoint] = None,
    ):
        self._journal = journal or ExecutionJournal()
        self._crash_points = crash_points or []
        self._current_operation: Optional[OperationRecord] = None
        self._original_sigterm = None
        self._original_sigint = None

    def execute_with_journal(
        self,
        run_id: str,
        session_id: str,
        capability_id: str,
        operation_type: OperationType,
        target: str,
        operation: Callable,
        arguments: Dict[str, Any] = None,
        parent_operation_id: str = None,
    ) -> Dict[str, Any]:
        """Execute an operation with full journaling.

        Args:
            run_id: The run ID
            session_id: The session ID
            capability_id: The capability being executed
            operation_type: The type of operation
            target: The target of the operation
            operation: The callable to execute
            arguments: Operation arguments
            parent_operation_id: Parent operation ID if any

        Returns:
            Dict with operation result
        """
        # Record intent
        intent_record = self._journal.record_intent(
            run_id=run_id,
            session_id=session_id,
            capability_id=capability_id,
            operation_type=operation_type.value,
            target=target,
            arguments=arguments,
            parent_operation_id=parent_operation_id,
        )

        # Check for crash point before start
        if CrashPoint.BEFORE_START in self._crash_points:
            self._crash("BEFORE_START")

        # Record start
        self._journal.record_start(run_id, intent_record.identity.operation_id)
        self._current_operation = intent_record

        # Check for crash point after start
        if CrashPoint.AFTER_START in self._crash_points:
            self._crash("AFTER_START")

        try:
            # Check for crash point during operation
            if CrashPoint.DURING_OPERATION in self._crash_points:
                self._crash("DURING_OPERATION")

            # Execute the operation
            result = operation()

            # Check for crash point after operation
            if CrashPoint.AFTER_OPERATION in self._crash_points:
                self._crash("AFTER_OPERATION")

            # Record completion
            self._journal.record_completion(
                run_id, intent_record.identity.operation_id, evidence={"result": str(result)}
            )

            # Check for crash point after completion
            if CrashPoint.AFTER_COMPLETION in self._crash_points:
                self._crash("AFTER_COMPLETION")

            return {
                "success": True,
                "operation_id": intent_record.identity.operation_id,
                "result": result,
            }

        except Exception as e:
            # Record failure
            self._journal.record_failure(
                run_id,
                intent_record.identity.operation_id,
                error=str(e),
                evidence={"exception_type": type(e).__name__},
            )
            return {
                "success": False,
                "operation_id": intent_record.identity.operation_id,
                "error": str(e),
            }

        finally:
            self._current_operation = None

    def add_crash_point(self, crash_point: CrashPoint):
        """Add a crash point for testing."""
        self._crash_points.append(crash_point)

    def clear_crash_points(self):
        """Clear all crash points."""
        self._crash_points.clear()

    def get_current_operation(self) -> Optional[OperationRecord]:
        """Get the currently executing operation."""
        return self._current_operation

    def _crash(self, point: str):
        """Simulate a process crash.

        This actually terminates the process to simulate real process death.
        """
        logger.warning(f"CRASH INJECTED at {point}")

        # Flush any pending writes
        sys.stdout.flush()
        sys.stderr.flush()

        # Terminate the process
        os._exit(1)


class CrashInjector:
    """Utility for injecting crashes at specific points."""

    def __init__(self):
        self._crash_points: List[CrashPoint] = []
        self._callbacks: Dict[CrashPoint, List[Callable]] = {}

    def register_crash_point(self, point: CrashPoint):
        """Register a crash point."""
        self._crash_points.append(point)

    def should_crash(self, point: CrashPoint) -> bool:
        """Check if a crash should occur at this point."""
        return point in self._crash_points

    def register_callback(self, point: CrashPoint, callback: Callable):
        """Register a callback to be called before crashing."""
        if point not in self._callbacks:
            self._callbacks[point] = []
        self._callbacks[point].append(callback)

    def execute_with_crash_detection(
        self,
        point: CrashPoint,
        operation: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute an operation with crash point detection.

        Args:
            point: The crash point to check
            operation: The operation to execute
            *args, **kwargs: Arguments for the operation

        Returns:
            Operation result

        Raises:
            SystemExit: If crash point is registered
        """
        if self.should_crash(point):
            # Execute callbacks before crashing
            callbacks = self._callbacks.get(point, [])
            for callback in callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Crash callback error: {e}")

            # Crash
            logger.warning(f"CRASH at {point.value}")
            os._exit(1)

        return operation(*args, **kwargs)
