"""
Tests for the explicit task state machine (Phase 6).

Covers:
- Valid/invalid state transitions
- Terminal states
- PlanStep lifecycle statuses
- Deterministic step selection
- State change events
"""

import pytest

from agentcore.task import (
    InvalidStateTransitionError,
    PlanStep,
    StepStatus,
    Task,
    TaskState,
)


class TestTaskStateMachineTransitions:
    def test_initial_state_is_created(self):
        task = Task()
        assert task.current_state == TaskState.CREATED

    def test_valid_created_to_analyzing(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        assert task.current_state == TaskState.ANALYZING

    def test_valid_analyzing_to_routing(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        assert task.current_state == TaskState.ROUTING

    def test_valid_routing_to_investigating(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        assert task.current_state == TaskState.INVESTIGATING

    def test_valid_investigating_to_planning(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        assert task.current_state == TaskState.PLANNING

    def test_valid_planning_to_running(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        assert task.current_state == TaskState.RUNNING

    def test_valid_running_to_waiting_for_tool(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.WAITING_FOR_TOOL)
        assert task.current_state == TaskState.WAITING_FOR_TOOL

    def test_valid_waiting_for_tool_to_observing(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.WAITING_FOR_TOOL)
        task.transition(TaskState.OBSERVING)
        assert task.current_state == TaskState.OBSERVING

    def test_valid_observing_to_running(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.WAITING_FOR_TOOL)
        task.transition(TaskState.OBSERVING)
        task.transition(TaskState.RUNNING)
        assert task.current_state == TaskState.RUNNING

    def test_valid_observing_to_replanning(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.WAITING_FOR_TOOL)
        task.transition(TaskState.OBSERVING)
        task.transition(TaskState.REPLANNING)
        assert task.current_state == TaskState.REPLANNING

    def test_valid_replanning_to_planning(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.WAITING_FOR_TOOL)
        task.transition(TaskState.OBSERVING)
        task.transition(TaskState.REPLANNING)
        task.transition(TaskState.PLANNING)
        assert task.current_state == TaskState.PLANNING

    def test_valid_running_to_verifying(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.VERIFYING)
        assert task.current_state == TaskState.VERIFYING

    def test_valid_verifying_to_completed(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.VERIFYING)
        task.transition(TaskState.COMPLETED)
        assert task.current_state == TaskState.COMPLETED

    def test_valid_verifying_to_replanning(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.VERIFYING)
        task.transition(TaskState.REPLANNING)
        assert task.current_state == TaskState.REPLANNING

    def test_valid_verifying_to_failed(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.VERIFYING)
        task.transition(TaskState.FAILED)
        assert task.current_state == TaskState.FAILED

    def test_valid_created_to_cancelled(self):
        task = Task()
        task.transition(TaskState.CANCELLED)
        assert task.current_state == TaskState.CANCELLED

    def test_valid_created_to_failed(self):
        task = Task()
        task.transition(TaskState.FAILED)
        assert task.current_state == TaskState.FAILED

    def test_valid_blocked_to_running(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.BLOCKED)
        task.transition(TaskState.RUNNING)
        assert task.current_state == TaskState.RUNNING

    def test_invalid_completed_to_running(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.VERIFYING)
        task.transition(TaskState.COMPLETED)
        with pytest.raises(InvalidStateTransitionError):
            task.transition(TaskState.RUNNING)

    def test_invalid_completed_to_failed(self):
        task = Task()
        task.transition(TaskState.ANALYZING)
        task.transition(TaskState.ROUTING)
        task.transition(TaskState.INVESTIGATING)
        task.transition(TaskState.PLANNING)
        task.transition(TaskState.RUNNING)
        task.transition(TaskState.VERIFYING)
        task.transition(TaskState.COMPLETED)
        with pytest.raises(InvalidStateTransitionError):
            task.transition(TaskState.FAILED)

    def test_invalid_failed_to_running(self):
        task = Task()
        task.transition(TaskState.FAILED)
        with pytest.raises(InvalidStateTransitionError):
            task.transition(TaskState.RUNNING)

    def test_invalid_cancelled_to_running(self):
        task = Task()
        task.transition(TaskState.CANCELLED)
        with pytest.raises(InvalidStateTransitionError):
            task.transition(TaskState.RUNNING)

    def test_invalid_direct_created_to_running(self):
        task = Task()
        with pytest.raises(InvalidStateTransitionError):
            task.transition(TaskState.RUNNING)

    def test_invalid_direct_created_to_verifying(self):
        task = Task()
        with pytest.raises(InvalidStateTransitionError):
            task.transition(TaskState.VERIFYING)

    def test_terminal_states_are_terminal(self):
        for state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            task = Task()
            if state == TaskState.COMPLETED:
                task.transition(TaskState.ANALYZING)
                task.transition(TaskState.ROUTING)
                task.transition(TaskState.INVESTIGATING)
                task.transition(TaskState.PLANNING)
                task.transition(TaskState.RUNNING)
                task.transition(TaskState.VERIFYING)
                task.transition(TaskState.COMPLETED)
            elif state == TaskState.FAILED:
                task.transition(TaskState.ANALYZING)
                task.transition(TaskState.FAILED)
            else:
                task.transition(TaskState.CANCELLED)
            assert task.is_terminal() is True

    def test_non_terminal_states_are_not_terminal(self):
        for state in [TaskState.RUNNING, TaskState.REPLANNING, TaskState.BLOCKED]:
            task = Task()
            task.transition(TaskState.ANALYZING)
            task.transition(TaskState.ROUTING)
            task.transition(TaskState.INVESTIGATING)
            task.transition(TaskState.PLANNING)
            if state == TaskState.RUNNING:
                task.transition(TaskState.RUNNING)
            elif state == TaskState.REPLANNING:
                task.transition(TaskState.RUNNING)
                task.transition(TaskState.WAITING_FOR_TOOL)
                task.transition(TaskState.OBSERVING)
                task.transition(TaskState.REPLANNING)
            else:
                task.transition(TaskState.RUNNING)
                task.transition(TaskState.BLOCKED)
            assert task.is_terminal() is False


class TestTaskStateChangeEvents:
    def test_state_changes_update_timestamp(self):
        import time

        task = Task()
        old_updated = task.updated_at
        time.sleep(0.01)
        task.transition(TaskState.ANALYZING)
        assert task.updated_at != old_updated

    def test_backward_compat_update_state(self):
        task = Task()
        task.update_state(TaskState.ANALYZING)
        assert task.current_state == TaskState.ANALYZING


class TestPlanStepLifecycle:
    def test_plan_step_default_status(self):
        step = PlanStep(action="inspect", description="Inspect code")
        assert step.status == StepStatus.PENDING

    def test_plan_step_to_dict(self):
        step = PlanStep(
            action="fix",
            description="Fix the bug",
            status=StepStatus.COMPLETED,
            outcome="Fixed",
            error=None,
            metadata={"attempt": 1},
        )
        data = step.to_dict()
        assert data["action"] == "fix"
        assert data["status"] == "COMPLETED"
        assert data["outcome"] == "Fixed"
        assert data["metadata"]["attempt"] == 1

    def test_plan_step_from_dict(self):
        data = {
            "action": "test",
            "description": "Run tests",
            "status": "FAILED",
            "outcome": None,
            "error": "tests failed",
            "metadata": {},
        }
        step = PlanStep.from_dict(data)
        assert step.action == "test"
        assert step.status == StepStatus.FAILED
        assert step.error == "tests failed"

    def test_plan_step_statuses(self):
        for status in StepStatus:
            step = PlanStep(action="act", description="desc", status=status)
            assert step.status == status

    def test_deterministic_next_step_selection(self):
        steps = [
            PlanStep(action="a", description="A", status=StepStatus.COMPLETED),
            PlanStep(action="b", description="B", status=StepStatus.PENDING),
            PlanStep(action="c", description="C", status=StepStatus.PENDING),
        ]
        task = Task()
        task.plan = [s.to_dict() for s in steps]
        next_step = task._select_next_step(steps)
        assert next_step.action == "b"

    def test_next_step_none_when_all_completed(self):
        steps = [
            PlanStep(action="a", description="A", status=StepStatus.COMPLETED),
            PlanStep(action="b", description="B", status=StepStatus.COMPLETED),
        ]
        task = Task()
        next_step = task._select_next_step(steps)
        assert next_step is None


class TestTaskSerialization:
    def test_serialization_to_dict(self):
        task = Task(user_request="Fix bug", project="test-project")
        task.transition(TaskState.ANALYZING)
        data = task.to_dict()
        assert data["current_state"] == "ANALYZING"
        assert data["user_request"] == "Fix bug"
        assert data["project"] == "test-project"

    def test_deserialization_from_dict(self):
        data = {
            "task_id": "task-abc123",
            "user_request": "Do something",
            "project": "my-project",
            "selected_skills": [],
            "project_context": {},
            "memory_context": {},
            "current_state": "COMPLETED",
            "plan": [],
            "actions": [],
            "tool_results": [],
            "changes": [],
            "test_results": {},
            "verification": {},
            "errors": [],
            "hypotheses": [],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        task = Task.from_dict(data)
        assert task.task_id == "task-abc123"
        assert task.current_state == TaskState.COMPLETED
