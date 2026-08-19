"""
DesktopTaskCoordinator — converts Hermes Desktop lifecycle events into
first-class Argus tasks.

Architecture
------------
    HermesEventBridge
        ↓
    Argus EventBus
        ↓
    DesktopTaskCoordinator  (this file)
        ↓
    TaskRegistry
        ↓
    TaskPersistenceManager
        ↓
    PersistenceBackend

The coordinator is responsible for:
* Maintaining the Hermes execution → Argus task identity mapping
* Registering new Argus tasks when Hermes emits TASK_REGISTERED
* Synchronizing Argus task state with Hermes lifecycle events
* Checkpointing tasks to persistence at terminal states

Identity model
--------------
One Hermes session produces multiple Argus tasks (one per turn).

    Hermes execution key  =  {session_id}:{task_id}
    Argus task_id         =  hermes-{session_id}-{task_id}

The Hermes `task_id` is the per-turn execution identifier emitted by the
HermesEventBridge.  It is preferred over `turn_id` because it is available
on every event.  `turn_id` and `session_key` are stored as task metadata
when available.

State mapping
-------------
    TASK_REGISTERED   →  TaskState.CREATED
    TASK_STARTED      →  TaskState.RUNNING
    TASK_COMPLETED    →  TaskState.COMPLETED
    TASK_FAILED       →  TaskState.FAILED
    TASK_CANCELLED    →  TaskState.CANCELLED
    TASK_STATE_CHANGED → update only when the Hermes event carries a
                         different state than the current Argus state

Failure isolation
-----------------
Every event handler catches exceptions and logs them.  A broken coordinator
cannot break Hermes execution because the HermesEventBridge already isolates
EventBus failures.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .control import ControlResult
from .events import AgentEvent, EventBus, EventType
from .harvesting import MemoryHarvester
from .memory import MemoryBackend
from .observations import ObservationCollector, ObservationStore
from .persistence import TaskPersistenceManager
from .task import Task, TaskState
from .task_registry import TaskRegistry

logger = logging.getLogger(__name__)


@dataclass
class HermesExecutionIdentity:
    """Identity of a single Hermes Desktop execution (one turn)."""

    session_id: str
    task_id: str = ""
    turn_id: str = ""
    session_key: str = ""

    def execution_key(self) -> str:
        """Stable key for deduplication and lookup."""
        return f"{self.session_id}:{self.task_id or self.session_id}"


@dataclass
class ArgusTaskIdentity:
    """Identity of the corresponding Argus task."""

    task_id: str
    hermes_session_id: str
    hermes_task_id: str
    hermes_turn_id: str = ""
    hermes_session_key: str = ""


class DesktopTaskCoordinator:
    """
    Converts Hermes Desktop EventBus events into Argus Task lifecycle changes
    and structured observations.

    The coordinator subscribes to the EventBus and reacts to a small set of
    lifecycle events.  It does NOT subscribe to tool/model events — those
    remain observations associated with the task.

    Architecture
    ------------
        HermesEventBridge
            ↓
        Argus EventBus
            ↓
        DesktopTaskCoordinator  (this file)
            ↓
        ├── TaskRegistry
        ├── TaskPersistenceManager
        └── ObservationCollector
            ↓
        ObservationStore
    """

    def __init__(
        self,
        task_registry: TaskRegistry,
        persistence: TaskPersistenceManager,
        event_bus: EventBus,
        control_bridge: Any | None = None,
        observation_store: ObservationStore | None = None,
        memory_backend: MemoryBackend | None = None,
    ) -> None:
        self._task_registry = task_registry
        self._persistence = persistence
        self._event_bus = event_bus
        self._control_bridge = control_bridge
        self._observation_collector = ObservationCollector(store=observation_store)
        self._execution_map: dict[str, ArgusTaskIdentity] = {}
        self._lock = threading.Lock()
        self._subscribed = False

        self._memory_backend = memory_backend
        self._harvester: MemoryHarvester | None = None
        if memory_backend is not None and observation_store is not None:
            self._harvester = MemoryHarvester(observation_store, memory_backend)

        self._harvest_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="harvest")
        self._harvested_tasks: set = set()
        self._harvest_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to the EventBus. Safe to call multiple times."""
        if self._subscribed:
            return
        try:
            self._event_bus.subscribe(self._on_event)
            self._subscribed = True
        except Exception:
            logger.debug("DesktopTaskCoordinator failed to subscribe", exc_info=True)

        try:
            self._observation_collector.start()
        except Exception:
            logger.debug("ObservationCollector failed to start", exc_info=True)

    def stop(self) -> None:
        """Unsubscribe from the EventBus and shutdown executor."""
        if not self._subscribed:
            return
        try:
            self._event_bus.unsubscribe(self._on_event)
        except Exception:
            pass
        self._subscribed = False

        try:
            self._harvest_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Control (Argus → Hermes)
    # ------------------------------------------------------------------

    def query_status(self, argus_task_id: str) -> ControlResult:
        """Query the current Hermes execution status for an Argus task."""
        identity = self.get_hermes_identity(argus_task_id)
        if identity is None:
            return ControlResult(
                outcome="NOT_FOUND",
                message="Argus task has no Hermes identity mapping",
                argus_task_id=argus_task_id,
            )

        if self._control_bridge is None:
            return ControlResult(
                outcome="NOT_FOUND",
                message="control bridge not available",
                argus_task_id=argus_task_id,
            )

        try:
            hermes_status = self._control_bridge.get_status(identity.hermes_session_id)
        except Exception as exc:
            return ControlResult(
                outcome="FAILED",
                message=f"control bridge error: {exc}",
                argus_task_id=argus_task_id,
            )

        hermes_state = hermes_status.get("status", "not_found")
        record = self._task_registry.get(argus_task_id)
        argus_state = record.task_state.value if record else None

        if argus_state in (
            TaskState.COMPLETED.value,
            TaskState.FAILED.value,
            TaskState.CANCELLED.value,
        ):
            return ControlResult(
                outcome="COMPLETED_ALREADY",
                message=f"task already in terminal state: {argus_state}",
                hermes_status=hermes_state,
                argus_task_id=argus_task_id,
                details={"argus_state": argus_state},
            )

        if hermes_state == "not_found":
            return ControlResult(
                outcome="NOT_FOUND",
                message="Hermes session not found",
                hermes_status=hermes_state,
                argus_task_id=argus_task_id,
            )

        return ControlResult(
            outcome="ACCEPTED",
            message=f"Hermes execution is {hermes_state}",
            hermes_status=hermes_state,
            argus_task_id=argus_task_id,
            details={"argus_state": argus_state},
        )

    def request_cancel(self, argus_task_id: str) -> ControlResult:
        """Request cancellation of a Hermes Desktop execution."""
        identity = self.get_hermes_identity(argus_task_id)
        if identity is None:
            return ControlResult(
                outcome="NOT_FOUND",
                message="Argus task has no Hermes identity mapping",
                argus_task_id=argus_task_id,
            )

        if self._control_bridge is None:
            return ControlResult(
                outcome="NOT_FOUND",
                message="control bridge not available",
                argus_task_id=argus_task_id,
            )

        record = self._task_registry.get(argus_task_id)
        argus_state = record.task_state.value if record else None

        if argus_state in (
            TaskState.COMPLETED.value,
            TaskState.FAILED.value,
            TaskState.CANCELLED.value,
        ):
            return ControlResult(
                outcome="COMPLETED_ALREADY",
                message=f"task already in terminal state: {argus_state}",
                argus_task_id=argus_task_id,
                details={"argus_state": argus_state},
            )

        try:
            hermes_result = self._control_bridge.cancel(identity.hermes_session_id)
        except Exception as exc:
            return ControlResult(
                outcome="FAILED",
                message=f"control bridge error: {exc}",
                argus_task_id=argus_task_id,
            )

        if not hermes_result.get("accepted", False):
            return ControlResult(
                outcome="REJECTED",
                message=hermes_result.get("message", "Hermes rejected cancellation"),
                hermes_status=hermes_result.get("hermes_status"),
                argus_task_id=argus_task_id,
                details=hermes_result,
            )

        return ControlResult(
            outcome="ACCEPTED",
            message=hermes_result.get("message", "cancellation requested"),
            hermes_status=hermes_result.get("hermes_status"),
            argus_task_id=argus_task_id,
            details=hermes_result,
        )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _on_event(self, event: AgentEvent) -> None:
        """EventBus subscriber callback. Failure-isolated."""
        try:
            self.handle_event(event)
        except Exception:
            logger.debug("DesktopTaskCoordinator dropped event", exc_info=True)

        try:
            identity = self._extract_identity(event)
            if identity is not None:
                argus_id = self._resolve_argus_task_id(identity)
                enriched_event = AgentEvent(
                    event_type=event.event_type,
                    task_id=argus_id,
                    data=event.data or {},
                    metadata={
                        **(event.metadata or {}),
                        "task_id": argus_id,
                        "session_id": identity.session_id,
                        "turn_id": identity.turn_id,
                        "tool_call_id": identity.task_id,
                    },
                    id=event.id,
                )
                self._observation_collector.handle_event(enriched_event)
        except Exception:
            logger.debug("ObservationCollector dropped event", exc_info=True)

        # Post-terminal hook: trigger harvesting after observation is recorded
        try:
            self._post_terminal_hook(event)
        except Exception:
            logger.debug("DesktopTaskCoordinator post-terminal hook failed", exc_info=True)

    def handle_event(self, event: AgentEvent) -> None:
        """Route a single EventBus event to the appropriate handler."""
        event_type = event.event_type
        if event_type not in (
            EventType.TASK_REGISTERED,
            EventType.TASK_STARTED,
            EventType.TASK_COMPLETED,
            EventType.TASK_FAILED,
            EventType.TASK_CANCELLED,
            EventType.TASK_STATE_CHANGED,
        ):
            return

        identity = self._extract_identity(event)
        if identity is None:
            logger.debug(
                "DesktopTaskCoordinator: no Hermes identity in event %s",
                event_type.value,
            )
            return

        argus_id = self._resolve_argus_task_id(identity)
        if argus_id is None:
            return

        if event_type == EventType.TASK_REGISTERED:
            self._handle_registered(argus_id, identity, event)
        elif event_type == EventType.TASK_STARTED:
            self._handle_started(argus_id, identity, event)
        elif event_type == EventType.TASK_COMPLETED:
            self._handle_completed(argus_id, identity, event)
        elif event_type == EventType.TASK_FAILED:
            self._handle_failed(argus_id, identity, event)
        elif event_type == EventType.TASK_CANCELLED:
            self._handle_cancelled(argus_id, identity, event)
        elif event_type == EventType.TASK_STATE_CHANGED:
            self._handle_state_changed(argus_id, identity, event)

    # ------------------------------------------------------------------
    # Identity extraction
    # ------------------------------------------------------------------

    def _extract_identity(self, event: AgentEvent) -> HermesExecutionIdentity | None:
        """Extract Hermes execution identity from an AgentEvent."""
        metadata = event.metadata or {}
        session_id = str(metadata.get("session_id") or "")
        if not session_id:
            return None
        task_id = str(metadata.get("task_id") or session_id)
        turn_id = str(metadata.get("turn_id") or "")
        session_key = str(metadata.get("session_key") or "")
        return HermesExecutionIdentity(
            session_id=session_id,
            task_id=task_id,
            turn_id=turn_id,
            session_key=session_key,
        )

    def _resolve_argus_task_id(self, identity: HermesExecutionIdentity) -> str | None:
        """Get or create the Argus task_id for a Hermes execution."""
        key = identity.execution_key()
        with self._lock:
            if key in self._execution_map:
                return self._execution_map[key].task_id
            argus_task_id = (
                f"hermes-{identity.session_id}-{identity.task_id or identity.session_id}"
            )
            self._execution_map[key] = ArgusTaskIdentity(
                task_id=argus_task_id,
                hermes_session_id=identity.session_id,
                hermes_task_id=identity.task_id or identity.session_id,
                hermes_turn_id=identity.turn_id,
                hermes_session_key=identity.session_key,
            )
            return argus_task_id

    def get_task_for_hermes_execution(self, session_id: str, task_id: str = "") -> str | None:
        """Look up the Argus task_id for a Hermes execution."""
        identity = HermesExecutionIdentity(session_id=session_id, task_id=task_id)
        key = identity.execution_key()
        with self._lock:
            mapping = self._execution_map.get(key)
            return mapping.task_id if mapping else None

    def get_hermes_identity(self, argus_task_id: str) -> ArgusTaskIdentity | None:
        """Reverse-lookup Hermes identity from an Argus task_id."""
        with self._lock:
            for identity in self._execution_map.values():
                if identity.task_id == argus_task_id:
                    return identity
        return None

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_registered(
        self, argus_task_id: str, identity: HermesExecutionIdentity, event: AgentEvent
    ) -> None:
        """Register a new Argus task for a Hermes execution."""
        existing = self._task_registry.get(argus_task_id)
        if existing is not None:
            logger.debug("Task %s already registered; skipping duplicate", argus_task_id)
            return

        task = Task(
            task_id=argus_task_id,
            user_request="",
            project="hermes_desktop",
            current_state=TaskState.CREATED,
            attributes=self._build_attributes(identity),
        )
        self._task_registry.register(task)
        if self._persistence is not None:
            self._persistence.checkpoint(task)
        logger.debug(
            "Registered Argus task %s for Hermes execution %s",
            argus_task_id,
            identity.execution_key(),
        )

    def _handle_started(
        self, argus_task_id: str, identity: HermesExecutionIdentity, event: AgentEvent
    ) -> None:
        """Transition an Argus task to RUNNING."""
        record = self._task_registry.get(argus_task_id)
        if record is None:
            self._register_or_skip(argus_task_id, identity, TaskState.RUNNING)
            return
        if record.task_state != TaskState.RUNNING:
            self._task_registry.update_task_state(argus_task_id, TaskState.RUNNING)
            task = self._load_task(argus_task_id)
            if task is not None:
                task.update_state(TaskState.RUNNING)
                if self._persistence is not None:
                    self._persistence.checkpoint(task)

    def _handle_completed(
        self, argus_task_id: str, identity: HermesExecutionIdentity, event: AgentEvent
    ) -> None:
        """Transition an Argus task to COMPLETED."""
        record = self._task_registry.get(argus_task_id)
        if record is None:
            self._register_or_skip(argus_task_id, identity, TaskState.COMPLETED)
            return
        if record.task_state != TaskState.COMPLETED:
            self._task_registry.update_task_state(argus_task_id, TaskState.COMPLETED)
            task = self._load_task(argus_task_id)
            if task is not None:
                task.update_state(TaskState.COMPLETED)
                if self._persistence is not None:
                    self._persistence.checkpoint(task)

    def _handle_failed(
        self, argus_task_id: str, identity: HermesExecutionIdentity, event: AgentEvent
    ) -> None:
        """Transition an Argus task to FAILED."""
        record = self._task_registry.get(argus_task_id)
        if record is None:
            self._register_or_skip(argus_task_id, identity, TaskState.FAILED)
            return
        if record.task_state != TaskState.FAILED:
            self._task_registry.update_task_state(argus_task_id, TaskState.FAILED)
            task = self._load_task(argus_task_id)
            if task is not None:
                task.update_state(TaskState.FAILED)
                if self._persistence is not None:
                    self._persistence.checkpoint(task)

    def _handle_cancelled(
        self, argus_task_id: str, identity: HermesExecutionIdentity, event: AgentEvent
    ) -> None:
        """Transition an Argus task to CANCELLED."""
        record = self._task_registry.get(argus_task_id)
        if record is None:
            self._register_or_skip(argus_task_id, identity, TaskState.CANCELLED)
            return
        if record.task_state != TaskState.CANCELLED:
            self._task_registry.update_task_state(argus_task_id, TaskState.CANCELLED)
            task = self._load_task(argus_task_id)
            if task is not None:
                task.update_state(TaskState.CANCELLED)
                if self._persistence is not None:
                    self._persistence.checkpoint(task)

    def _handle_state_changed(
        self, argus_task_id: str, identity: HermesExecutionIdentity, event: AgentEvent
    ) -> None:
        """Handle a generic state change event."""
        data = event.data or {}
        new_state_str = data.get("current_state")
        if not new_state_str:
            return
        try:
            new_state = TaskState(new_state_str)
        except ValueError:
            return
        record = self._task_registry.get(argus_task_id)
        if record is None:
            self._register_or_skip(argus_task_id, identity, new_state)
            return
        if record.task_state != new_state:
            self._task_registry.update_task_state(argus_task_id, new_state)
            task = self._load_task(argus_task_id)
            if task is not None:
                task.update_state(new_state)
                if self._persistence is not None:
                    self._persistence.checkpoint(task)

    # ------------------------------------------------------------------
    # Harvesting integration
    # ------------------------------------------------------------------

    def harvest_task(self, task_id: str) -> dict[str, Any] | None:
        """
        Manually trigger memory harvesting for a task.

        Returns the HarvestResult dict or None if harvesting is not available.
        Safe to call repeatedly.
        """
        if self._harvester is None:
            return None
        try:
            result = self._harvester.harvest_task(task_id)
            return {
                "task_id": result.task_id,
                "candidates": [
                    {
                        "id": c.id,
                        "memory_type": c.memory_type,
                        "content": c.content,
                        "source_observation_ids": c.source_observation_ids,
                    }
                    for c in result.candidates
                ],
                "observations_processed": result.observations_processed,
                "skipped_count": result.skipped_count,
                "error_count": len(result.errors),
                "errors": result.errors,
                "harvested_at": result.harvested_at,
            }
        except Exception as e:
            logger.debug("Manual harvest failed for %s: %s", task_id, e, exc_info=True)
            return None

    def _post_terminal_hook(self, event: AgentEvent) -> None:
        """Trigger harvesting for terminal task events."""
        if self._harvester is None:
            return
        if event.event_type not in (
            EventType.TASK_COMPLETED,
            EventType.TASK_FAILED,
            EventType.TASK_CANCELLED,
        ):
            return

        identity = self._extract_identity(event)
        if identity is None:
            return

        argus_id = self._resolve_argus_task_id(identity)
        if argus_id is None:
            return

        with self._harvest_lock:
            if argus_id in self._harvested_tasks:
                return
            self._harvested_tasks.add(argus_id)

        try:
            future = self._harvest_executor.submit(self._do_harvest, argus_id, event.event_type)
            future.add_done_callback(self._harvest_done)
        except Exception:
            logger.debug("Failed to submit harvest for %s", argus_id, exc_info=True)

    def _do_harvest(self, task_id: str, event_type: EventType) -> dict[str, Any]:
        """Execute harvesting in a worker thread. Never raises."""
        try:
            result = self._harvester.harvest_task(task_id)
            success = len(result.errors) == 0
            return {
                "task_id": task_id,
                "event_type": event_type,
                "success": success,
                "candidate_count": len(result.candidates),
                "observations_processed": result.observations_processed,
                "skipped_count": result.skipped_count,
                "error_count": len(result.errors),
                "errors": result.errors,
                "harvested_at": result.harvested_at,
            }
        except Exception as e:
            logger.debug("Harvest failed for %s: %s", task_id, e, exc_info=True)
            return {
                "task_id": task_id,
                "event_type": event_type,
                "success": False,
                "candidate_count": 0,
                "observations_processed": 0,
                "skipped_count": 0,
                "error_count": 1,
                "errors": [str(e)],
                "harvested_at": datetime.now(UTC).isoformat(),
            }

    def _harvest_done(self, future) -> None:
        """Callback when a harvest future completes."""
        try:
            result = future.result()
        except Exception as e:
            logger.debug("Harvest future raised: %s", e, exc_info=True)
            return

        try:
            if result.get("success"):
                self._event_bus.emit(
                    AgentEvent(
                        event_type=EventType.MEMORY_HARVEST_COMPLETED,
                        task_id=result.get("task_id", ""),
                        data={
                            "candidate_count": result.get("candidate_count", 0),
                            "observations_processed": result.get("observations_processed", 0),
                            "skipped_count": result.get("skipped_count", 0),
                            "error_count": result.get("error_count", 0),
                        },
                        metadata={"success": True},
                    )
                )
            else:
                self._event_bus.emit(
                    AgentEvent(
                        event_type=EventType.MEMORY_HARVEST_FAILED,
                        task_id=result.get("task_id", ""),
                        data={
                            "error_count": result.get("error_count", 0),
                            "errors": result.get("errors", []),
                        },
                        metadata={"success": False},
                    )
                )
        except Exception:
            logger.debug("Failed to emit harvest event", exc_info=True)

    def _build_attributes(self, identity: HermesExecutionIdentity) -> dict[str, Any]:
        """Build task attributes from Hermes identity."""
        attrs: dict[str, Any] = {
            "source": "hermes_desktop",
            "runtime": "hermes",
            "hermes_session_id": identity.session_id,
            "hermes_task_id": identity.task_id or identity.session_id,
        }
        if identity.turn_id:
            attrs["hermes_turn_id"] = identity.turn_id
        if identity.session_key:
            attrs["hermes_session_key"] = identity.session_key
        return attrs

    def _register_or_skip(
        self,
        argus_task_id: str,
        identity: HermesExecutionIdentity,
        initial_state: TaskState,
    ) -> None:
        """Register a task only if it doesn't already exist."""
        if self._task_registry.get(argus_task_id) is not None:
            return
        task = Task(
            task_id=argus_task_id,
            user_request="",
            project="hermes_desktop",
            current_state=initial_state,
            attributes=self._build_attributes(identity),
        )
        self._task_registry.register(task)
        self._persistence.checkpoint(task)

    def _load_task(self, task_id: str) -> Task | None:
        """Load a task from persistence, falling back to registry reconstruction."""
        task = self._persistence.load_task(task_id)
        if task is not None:
            return task
        record = self._task_registry.get(task_id)
        if record is None:
            return None
        return Task(
            task_id=record.task_id,
            user_request=record.user_request,
            project=record.project,
            current_state=record.task_state,
            attributes=record.metadata,
        )
