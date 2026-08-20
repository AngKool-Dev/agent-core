import pytest
from agentcore import Task, TaskState


class TestTaskStateTransitions:
    def test_initial_state_is_created(self):
        task = Task()
        assert task.current_state == TaskState.CREATED

    def test_state_transitions(self):
        task = Task()
        task.update_state(TaskState.ANALYZING)
        assert task.current_state == TaskState.ANALYZING
        task.update_state(TaskState.ROUTING)
        assert task.current_state == TaskState.ROUTING

    def test_state_changes_updated_at(self):
        import time
        task = Task()
        old_updated = task.updated_at
        time.sleep(0.01)
        task.update_state(TaskState.COMPLETED)
        assert task.updated_at != old_updated

    def test_serialization_to_dict(self):
        task = Task(user_request="Fix bug", project="test-project")
        task.update_state(TaskState.COMPLETED)
        data = task.to_dict()
        
        assert data["current_state"] == "COMPLETED"
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


class TestTaskStates:
    def test_all_valid_states(self):
        states = [TaskState.CREATED, TaskState.ANALYZING, TaskState.ROUTING,
                  TaskState.INVESTIGATING, TaskState.PLANNING, TaskState.IMPLEMENTING,
                  TaskState.VERIFYING, TaskState.COMPLETED, TaskState.FAILED, TaskState.BLOCKED]
        for state in states:
            task = Task()
            task.update_state(state)
            assert task.current_state == state


class TestTaskWithHypotheses:
    def test_hypothesis_tracking(self):
        task = Task()
        task.hypotheses.append({
            "statement": "The bug is in the parser",
            "supporting_evidence": ["Error occurs in parsing phase"],
            "contradicting_evidence": [],
            "status": "PROPOSED",
        })
        assert len(task.hypotheses) == 1
        assert task.hypotheses[0]["status"] == "PROPOSED"