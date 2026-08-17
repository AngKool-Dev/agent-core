"""
AgentCore lifecycle management (Phase 8).

Provides:
- AgentCore class: facade for multi-task execution, shutdown, recovery
- Configuration validation
- Resource limit enforcement
- Lifecycle event emission
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import AgentCoreConfig, ConfigLoader, ToolLimits
from .errors import ConfigurationError
from .events import EventBus, EventType, create_event
from .persistence import TaskPersistenceManager, create_persistence_manager
from .task import Task, TaskState
from .task_registry import TaskRegistry, TaskRecord, TaskRecordStatus


@dataclass
class AgentCoreLimits:
    """Production resource limits."""
    max_active_tasks: int = 10
    max_task_execution_seconds: int = 600
    max_task_lifetime_seconds: int = 3600
    max_recovery_tasks: int = 100
    max_event_history: int = 1000
    max_persisted_task_size_bytes: int = 1024 * 1024  # 1 MB

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_active_tasks": self.max_active_tasks,
            "max_task_execution_seconds": self.max_task_execution_seconds,
            "max_task_lifetime_seconds": self.max_task_lifetime_seconds,
            "max_recovery_tasks": self.max_recovery_tasks,
            "max_event_history": self.max_event_history,
            "max_persisted_task_size_bytes": self.max_persisted_task_size_bytes,
        }

    def validate(self) -> None:
        """Validate limits and raise ConfigurationError if invalid."""
        if self.max_active_tasks < 1:
            raise ConfigurationError("max_active_tasks", "must be >= 1")
        if self.max_task_execution_seconds < 1:
            raise ConfigurationError("max_task_execution_seconds", "must be >= 1")
        if self.max_task_lifetime_seconds < 1:
            raise ConfigurationError("max_task_lifetime_seconds", "must be >= 1")
        if self.max_recovery_tasks < 1:
            raise ConfigurationError("max_recovery_tasks", "must be >= 1")
        if self.max_event_history < 1:
            raise ConfigurationError("max_event_history", "must be >= 1")
        if self.max_persisted_task_size_bytes < 1024:
            raise ConfigurationError("max_persisted_task_size_bytes", "must be >= 1024")


class AgentCore:
    """
    Facade for AgentCore lifecycle management.

    Responsibilities:
    - Own Agent instances
    - Track active tasks via TaskRegistry
    - Coordinate persistence via TaskPersistenceManager
    - Manage graceful shutdown
    - Emit lifecycle events via EventBus
    - Enforce resource limits
    - Validate configuration
    """

    def __init__(
        self,
        config: Optional[AgentCoreConfig] = None,
        persistence: Optional[TaskPersistenceManager] = None,
        event_bus: Optional[EventBus] = None,
        limits: Optional[AgentCoreLimits] = None,
        project_path: Optional[Path] = None,
    ):
        self._config = config or ConfigLoader.discover(project_path or Path.cwd())
        self._persistence = persistence or create_persistence_manager()
        self._event_bus = event_bus or EventBus()
        self._limits = limits or AgentCoreLimits()

        try:
            self._limits.validate()
        except ConfigurationError:
            raise

        self._registry = TaskRegistry(
            persistence=self._persistence,
            event_bus=self._event_bus,
        )

        self._project_path = project_path or Path.cwd()
        self._active_agents: Dict[str, Any] = {}  # task_id -> Agent
        self._shutdown_requested = False
        self._shutdown_lock = threading.RLock()
        self._started_at = datetime.now(timezone.utc).isoformat()

    @property
    def config(self) -> AgentCoreConfig:
        return self._config

    @property
    def persistence(self) -> TaskPersistenceManager:
        return self._persistence

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def registry(self) -> TaskRegistry:
        return self._registry

    @property
    def limits(self) -> AgentCoreLimits:
        return self._limits

    @property
    def started_at(self) -> str:
        return self._started_at

    def _emit(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> None:
        if self._event_bus is None or self._event_bus.subscriber_count == 0:
            return
        try:
            event = create_event(
                event_type=event_type,
                task_id=data.get("task_id", "") if data else "",
                data=data or {},
            )
            self._event_bus.emit(event)
        except Exception:
            pass

    def shutdown(self) -> Dict[str, Any]:
        """
        Graceful shutdown.

        - Stop accepting new work
        - Checkpoint active tasks
        - Release locks
        - Close persistence
        - Emit shutdown events
        """
        with self._shutdown_lock:
            self._shutdown_requested = True
            self._emit(EventType.SHUTDOWN_STARTED, data={})

            checkpointed = 0
            cancelled = 0
            errors: List[str] = []

            for record in self._registry.list_active():
                try:
                    if self._persistence is not None and hasattr(self._persistence, 'checkpoint'):
                        task = self._persistence.load_task(record.task_id)
                        if task is not None and not task.is_terminal():
                            self._persistence.checkpoint(task)
                            checkpointed += 1
                    self._registry.force_release_lock(record.task_id)
                    cancelled += 1
                except Exception as e:
                    errors.append(f"{record.task_id}: {e}")

            if self._persistence is not None and hasattr(self._persistence, 'close'):
                try:
                    self._persistence.close()
                except Exception as e:
                    errors.append(f"persistence_close: {e}")

            self._registry.close()

            result = {
                "shutdown": True,
                "checkpointed": checkpointed,
                "cancelled": cancelled,
                "errors": errors,
            }
            self._emit(EventType.SHUTDOWN_COMPLETED, data=result)
            return result

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    def recover_tasks(self) -> List[TaskRecord]:
        """
        Discover and recover incomplete tasks from persistence.

        Returns list of recovered TaskRecord objects.
        """
        self._emit(EventType.RECOVERY_STARTED, data={})
        try:
            recovered = self._registry.recover_from_persistence(self._persistence)
            self._emit(EventType.RECOVERY_COMPLETED, data={
                "recovered_count": len(recovered),
            })
            return recovered
        except Exception as e:
            self._emit(EventType.RECOVERY_FAILED, data={"error": str(e)})
            raise

    def register_agent(self, task_id: str, agent: Any) -> TaskRecord:
        """Register an agent instance for tracking."""
        if self._shutdown_requested:
            raise RuntimeError("AgentCore is shutting down; not accepting new work")

        if len(self._registry.list_active()) >= self._limits.max_active_tasks:
            raise RuntimeError(f"Active task limit ({self._limits.max_active_tasks}) reached")

        task = getattr(agent, 'current_task', None)
        if task is None:
            raise ValueError("Agent has no current task")

        record = self._registry.register(task)
        self._active_agents[task_id] = agent
        return record

    def unregister_agent(self, task_id: str) -> None:
        """Unregister an agent after completion."""
        self._active_agents.pop(task_id, None)

    def get_active_agent(self, task_id: str) -> Optional[Any]:
        """Get an active agent by task ID."""
        return self._active_agents.get(task_id)

    def list_active_agents(self) -> Dict[str, Any]:
        """List all active agents."""
        return dict(self._active_agents)

    def close(self) -> None:
        """Close all resources."""
        self.shutdown()


def create_agent_core(
    config: Optional[AgentCoreConfig] = None,
    persistence: Optional[TaskPersistenceManager] = None,
    event_bus: Optional[EventBus] = None,
    project_path: Optional[Path] = None,
) -> AgentCore:
    """Factory for AgentCore."""
    return AgentCore(
        config=config,
        persistence=persistence,
        event_bus=event_bus,
        project_path=project_path,
    )
