"""
Structured error taxonomy for AgentCore Phase 8.

Provides provider-neutral exceptions with structured information.
No secrets are leaked in error messages.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AgentCoreError(Exception):
    """Base exception for all AgentCore errors."""

    def __init__(self, message: str = "", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": str(self),
            "details": self.details,
        }


class TaskAlreadyRunningError(AgentCoreError):
    """Raised when attempting to execute a task that is already running."""

    def __init__(self, task_id: str, message: str = ""):
        super().__init__(message or f"Task {task_id} is already running")
        self.details = {"task_id": task_id}


class TaskNotFoundError(AgentCoreError):
    """Raised when a task cannot be found."""

    def __init__(self, task_id: str, message: str = ""):
        super().__init__(message or f"Task {task_id} not found")
        self.details = {"task_id": task_id}


class TaskRecoveryError(AgentCoreError):
    """Raised when task recovery fails."""

    def __init__(self, task_id: str, reason: str = "", message: str = ""):
        super().__init__(message or f"Failed to recover task {task_id}: {reason}")
        self.details = {"task_id": task_id, "reason": reason}


class TaskLockError(AgentCoreError):
    """Raised when a task lock cannot be acquired or released."""

    def __init__(self, task_id: str, operation: str, message: str = ""):
        super().__init__(message or f"Task {task_id} lock {operation} failed")
        self.details = {"task_id": task_id, "operation": operation}


class ShutdownError(AgentCoreError):
    """Raised when shutdown fails."""

    def __init__(self, reason: str = "", message: str = ""):
        super().__init__(message or f"Shutdown failed: {reason}")
        self.details = {"reason": reason}


class ConfigurationError(AgentCoreError):
    """Raised when configuration is invalid."""

    def __init__(self, field: str, reason: str = "", message: str = ""):
        super().__init__(message or f"Invalid configuration for {field}: {reason}")
        self.details = {"field": field, "reason": reason}
