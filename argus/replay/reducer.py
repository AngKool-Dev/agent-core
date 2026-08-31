"""ARGUS Replay state reducer - reconstructs logical state from events."""

import copy
import logging
from typing import Any, Dict, List, Optional

from argus.replay.models import (
    ReplayEvent,
    ReplayRun,
)

logger = logging.getLogger(__name__)


class StateReducer:
    """Reconstructs logical state from events and checkpoints.

    The reducer is deterministic - running the same events twice
    produces equivalent state.
    """

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._event_log: List[str] = []

    def reduce(self, run: ReplayRun) -> Dict[str, Any]:
        """Reduce a replay run to its final state.

        Args:
            run: The replay run to reduce

        Returns:
            The reconstructed final state
        """
        # Start with initial state
        state = copy.deepcopy(run.initial_state)

        # Apply checkpoints first (they provide known-good states)
        for checkpoint in run.checkpoints:
            state = self._apply_checkpoint(state, checkpoint)

        # Apply events in order
        for event in run.events:
            state = self._apply_event(state, event)

        return state

    def reduce_to_checkpoint(self, run: ReplayRun, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Reduce state up to a specific checkpoint.

        Args:
            run: The replay run
            checkpoint_id: The checkpoint ID to stop at

        Returns:
            The state at the checkpoint, or None if not found
        """
        state = copy.deepcopy(run.initial_state)

        for checkpoint in run.checkpoints:
            state = self._apply_checkpoint(state, checkpoint)
            if checkpoint.checkpoint_id == checkpoint_id:
                return state

        return None

    def reduce_to_event(self, run: ReplayRun, sequence: int) -> Dict[str, Any]:
        """Reduce state up to a specific event sequence.

        Args:
            run: The replay run
            sequence: The event sequence number to stop at

        Returns:
            The state after applying events up to the sequence
        """
        state = copy.deepcopy(run.initial_state)

        for event in run.events:
            if event.sequence <= sequence:
                state = self._apply_event(state, event)
            else:
                break

        return state

    def _apply_checkpoint(self, state: Dict[str, Any], checkpoint) -> Dict[str, Any]:
        """Apply a checkpoint to the state."""
        new_state = copy.deepcopy(state)
        new_state.update(checkpoint.state)
        new_state["_last_checkpoint"] = checkpoint.checkpoint_id
        new_state["_checkpoint_sequence"] = checkpoint.sequence
        return new_state

    def _apply_event(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        """Apply an event to the state."""
        new_state = copy.deepcopy(state)

        handler = self._get_handler(event.event_type)
        if handler:
            new_state = handler(new_state, event)

        # Track event application
        new_state["_last_event"] = event.event_id
        new_state["_last_event_sequence"] = event.sequence

        return new_state

    def _get_handler(self, event_type: str):
        """Get the handler for an event type."""
        handlers = {
            "agent.started": self._handle_agent_started,
            "agent.completed": self._handle_agent_completed,
            "agent.failed": self._handle_agent_failed,
            "agent.paused": self._handle_agent_paused,
            "agent.resumed": self._handle_agent_resumed,
            "task.received": self._handle_task_received,
            "plan.created": self._handle_plan_created,
            "plan.revised": self._handle_plan_revised,
            "step.started": self._handle_step_started,
            "step.completed": self._handle_step_completed,
            "capability.started": self._handle_capability_started,
            "capability.completed": self._handle_capability_completed,
            "capability.failed": self._handle_capability_failed,
            "execution.started": self._handle_execution_started,
            "execution.completed": self._handle_execution_completed,
            "execution.failed": self._handle_execution_failed,
            "verification.started": self._handle_verification_started,
            "verification.completed": self._handle_verification_completed,
            "verification.failed": self._handle_verification_failed,
            "recovery.started": self._handle_recovery_started,
            "recovery.completed": self._handle_recovery_completed,
            "recovery.exhausted": self._handle_recovery_exhausted,
            "security.allowed": self._handle_security_decision,
            "security.denied": self._handle_security_decision,
            "security.approval_requested": self._handle_security_decision,
            "security.approved": self._handle_security_decision,
            "security.rejected": self._handle_security_decision,
            "security.injection_detected": self._handle_security_decision,
            "model.requested": self._handle_model_event,
            "model.completed": self._handle_model_event,
            "model.failed": self._handle_model_event,
            "model.fallback": self._handle_model_event,
        }
        return handlers.get(event_type)

    def _handle_agent_started(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["agent_status"] = "started"
        if event.run_id:
            state["run_id"] = event.run_id
        return state

    def _handle_agent_completed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["agent_status"] = "completed"
        state["completed_at"] = event.timestamp
        return state

    def _handle_agent_failed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["agent_status"] = "failed"
        state["failed_at"] = event.timestamp
        if event.metadata:
            state["failure_reason"] = event.metadata.get("reason", "unknown")
        return state

    def _handle_agent_paused(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["agent_status"] = "paused"
        return state

    def _handle_agent_resumed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["agent_status"] = "resumed"
        return state

    def _handle_task_received(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if event.payload:
            state["task"] = event.payload.get("task", "")
        return state

    def _handle_plan_created(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if event.metadata:
            state["plan"] = event.metadata.get("steps", [])
        return state

    def _handle_plan_revised(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if event.metadata:
            state["plan"] = event.metadata.get("steps", [])
            state["plan_revised"] = True
        return state

    def _handle_step_started(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if event.metadata:
            state["current_step"] = event.metadata.get("step_id")
        return state

    def _handle_step_completed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if "completed_steps" not in state:
            state["completed_steps"] = []
        if event.metadata:
            state["completed_steps"].append(event.metadata.get("step_id"))
        return state

    def _handle_capability_started(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["current_capability"] = event.capability
        state["capability_status"] = "started"
        return state

    def _handle_capability_completed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["capability_status"] = "completed"
        if "capabilities_used" not in state:
            state["capabilities_used"] = []
        if event.capability:
            state["capabilities_used"].append(event.capability)
        return state

    def _handle_capability_failed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["capability_status"] = "failed"
        if "capability_failures" not in state:
            state["capability_failures"] = []
        if event.capability:
            state["capability_failures"].append(event.capability)
        return state

    def _handle_execution_started(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["execution_status"] = "started"
        return state

    def _handle_execution_completed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["execution_status"] = "completed"
        return state

    def _handle_execution_failed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["execution_status"] = "failed"
        return state

    def _handle_verification_started(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["verification_status"] = "started"
        return state

    def _handle_verification_completed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["verification_status"] = "completed"
        if event.metadata:
            state["verification_result"] = event.metadata.get("result", "passed")
        return state

    def _handle_verification_failed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["verification_status"] = "failed"
        return state

    def _handle_recovery_started(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["recovery_status"] = "started"
        if "recovery_attempts" not in state:
            state["recovery_attempts"] = 0
        state["recovery_attempts"] += 1
        return state

    def _handle_recovery_completed(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["recovery_status"] = "completed"
        return state

    def _handle_recovery_exhausted(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        state["recovery_status"] = "exhausted"
        return state

    def _handle_security_decision(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if "security_decisions" not in state:
            state["security_decisions"] = []
        state["security_decisions"].append({
            "type": event.event_type,
            "capability": event.capability,
            "timestamp": event.timestamp,
        })
        return state

    def _handle_model_event(self, state: Dict[str, Any], event: ReplayEvent) -> Dict[str, Any]:
        if "model_events" not in state:
            state["model_events"] = []
        state["model_events"].append({
            "type": event.event_type,
            "timestamp": event.timestamp,
        })
        return state


def reduce_run(run: ReplayRun) -> Dict[str, Any]:
    """Convenience function to reduce a run to its final state."""
    reducer = StateReducer()
    return reducer.reduce(run)
