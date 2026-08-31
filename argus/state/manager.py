"""State manager - orchestrates agent state lifecycle."""

import time
from typing import Any, Dict, List, Optional

from argus.state.models import AgentState, PlanStep, RunStatus
from argus.state.store import StateStore


class StateManager:
    """Manages agent state lifecycle."""

    def __init__(self, state_store: Optional[StateStore] = None):
        self._store = state_store
        self._active_states: Dict[str, AgentState] = {}

    @property
    def has_store(self) -> bool:
        return self._store is not None

    def create_state(
        self,
        task: str,
        project_path: str = "",
        session_id: str = "",
        plan: List[Dict[str, Any]] = None,
    ) -> AgentState:
        """Create a new agent state."""
        state = AgentState(
            task=task,
            project_id=project_path,
            session_id=session_id,
            status=RunStatus.PENDING,
        )

        # Add plan steps
        if plan:
            for step_data in plan:
                state.add_plan_step(
                    description=step_data.get("description", ""),
                    capability_id=step_data.get("capability_id", ""),
                    input_data=step_data.get("input_data", {}),
                )

        # Set first step as current
        if state.plan:
            state.current_step_id = state.plan[0].id
            state.plan[0].status = "active"

        state.status = RunStatus.RUNNING
        state.current_phase = "starting"

        # Persist
        self._persist(state)
        self._active_states[state.run_id] = state

        return state

    def get_state(self, run_id: str) -> Optional[AgentState]:
        """Get a state by run ID."""
        # Check active states first
        if run_id in self._active_states:
            return self._active_states[run_id]

        # Load from store
        if self._store:
            state = self._store.load_state(run_id)
            if state:
                self._active_states[run_id] = state
                return state

        return None

    def update_state(self, state: AgentState) -> None:
        """Update a state."""
        state.update()
        self._persist(state)
        self._active_states[state.run_id] = state

    def set_phase(self, run_id: str, phase: str) -> None:
        """Set the current phase."""
        state = self.get_state(run_id)
        if state:
            state.current_phase = phase
            self.update_state(state)

    def set_step_status(
        self,
        run_id: str,
        step_id: str,
        status: str,
        output: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """Set a step's status."""
        state = self.get_state(run_id)
        if state:
            state.set_step_status(step_id, status, output, error)
            self.update_state(state)

    def advance_step(self, run_id: str) -> Optional[PlanStep]:
        """Advance to the next pending step."""
        state = self.get_state(run_id)
        if not state:
            return None

        # Mark current step as completed
        current = state.current_step
        if current and current.status == "active":
            current.status = "completed"

        # Find next pending step
        next_step = None
        for step in state.plan:
            if step.status == "pending":
                next_step = step
                break

        if next_step:
            next_step.status = "active"
            state.current_step_id = next_step.id
        else:
            state.current_step_id = None
            state.status = RunStatus.COMPLETED

        self.update_state(state)
        return next_step

    def add_execution_record(self, run_id: str, record: Dict[str, Any]) -> None:
        """Add an execution record."""
        state = self.get_state(run_id)
        if state:
            state.add_execution_record(record)
            self.update_state(state)

    def add_verification_result(self, run_id: str, result: Dict[str, Any]) -> None:
        """Add a verification result."""
        state = self.get_state(run_id)
        if state:
            state.add_verification_result(result)
            self.update_state(state)

    def set_recovery_state(self, run_id: str, recovery_state: Dict[str, Any]) -> None:
        """Set recovery state."""
        state = self.get_state(run_id)
        if state:
            state.set_recovery_state(recovery_state)
            self.update_state(state)

    def set_recovery_budget(self, run_id: str, budget: Dict[str, Any]) -> None:
        """Set recovery budget."""
        state = self.get_state(run_id)
        if state:
            state.set_recovery_budget(budget)
            self.update_state(state)

    def add_assumption(self, run_id: str, assumption: str, valid: bool = True) -> None:
        """Add an assumption."""
        state = self.get_state(run_id)
        if state:
            state.add_assumption(assumption, valid)
            self.update_state(state)

    def invalidate_assumption(self, run_id: str, assumption: str) -> None:
        """Invalidate an assumption."""
        state = self.get_state(run_id)
        if state:
            state.invalidate_assumption(assumption)
            self.update_state(state)

    def add_learned_fact(self, run_id: str, fact: str) -> None:
        """Add a learned fact."""
        state = self.get_state(run_id)
        if state:
            state.add_learned_fact(fact)
            self.update_state(state)

    def complete_run(self, run_id: str) -> None:
        """Mark a run as completed."""
        state = self.get_state(run_id)
        if state:
            state.complete()
            self.update_state(state)
            self._active_states.pop(run_id, None)

    def fail_run(self, run_id: str) -> None:
        """Mark a run as failed."""
        state = self.get_state(run_id)
        if state:
            state.fail()
            self.update_state(state)
            self._active_states.pop(run_id, None)

    def pause_run(self, run_id: str) -> None:
        """Pause a run."""
        state = self.get_state(run_id)
        if state:
            state.status = RunStatus.PAUSED
            self.update_state(state)

    def resume_run(self, run_id: str) -> Optional[AgentState]:
        """Resume a paused run."""
        state = self.get_state(run_id)
        if state and state.status == RunStatus.PAUSED:
            state.status = RunStatus.RUNNING
            state.current_phase = "resuming"
            self.update_state(state)
            return state
        return None

    def get_latest_running(self) -> Optional[AgentState]:
        """Get the latest running state."""
        if self._store:
            return self._store.get_latest_running()
        return None

    def list_states(self, status: Optional[RunStatus] = None, limit: int = 20) -> List[AgentState]:
        """List states."""
        if self._store:
            return self._store.list_states(status=status, limit=limit)
        return []

    def _persist(self, state: AgentState) -> None:
        """Persist state to store."""
        if self._store:
            self._store.save_state(state)