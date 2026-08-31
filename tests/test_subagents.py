"""Tests for ARGUS Subagents."""

import time
import pytest

from argus.subagents import (
    AggregationResult,
    ResultAggregator,
    Subagent,
    SubagentBudget,
    SubagentContext,
    SubagentId,
    SubagentManager,
    SubagentOrchestrator,
    SubagentResult,
    SubagentRole,
    SubagentStatus,
    SubagentTask,
    create_budget,
    create_context,
    create_contract,
    create_orchestrator,
    derive_child_budget,
    get_role_definition,
    is_valid_transition,
)


class TestSubagentModels:
    def test_subagent_id_generation(self):
        id1 = SubagentId.generate()
        id2 = SubagentId.generate()
        assert str(id1) != str(id2)

    def test_subagent_creation(self):
        subagent = Subagent(
            role=SubagentRole.RESEARCHER,
            objective="Test objective",
        )
        assert subagent.status == SubagentStatus.CREATED
        assert subagent.role == SubagentRole.RESEARCHER
        assert subagent.is_active is False
        assert subagent.is_terminal is False

    def test_subagent_is_active(self):
        subagent = Subagent(status=SubagentStatus.RUNNING)
        assert subagent.is_active is True

    def test_subagent_is_terminal(self):
        subagent = Subagent(status=SubagentStatus.COMPLETED)
        assert subagent.is_terminal is True

    def test_subagent_duration(self):
        subagent = Subagent(
            status=SubagentStatus.COMPLETED,
            started_at=100.0,
            completed_at=105.0,
        )
        assert subagent.duration == 5.0

    def test_subagent_to_dict(self):
        subagent = Subagent(
            role=SubagentRole.RESEARCHER,
            objective="Test",
        )
        d = subagent.to_dict()
        assert d["role"] == "researcher"
        assert d["objective"] == "Test"

    def test_subagent_task_creation(self):
        task = SubagentTask(
            objective="Test task",
            role=SubagentRole.IMPLEMENTER,
        )
        assert task.task_id is not None
        assert task.role == SubagentRole.IMPLEMENTER

    def test_subagent_result_creation(self):
        result = SubagentResult(
            subagent_id="test-123",
            status=SubagentStatus.COMPLETED,
            summary="Done",
        )
        assert result.is_success is True
        assert result.has_findings is False

    def test_subagent_result_has_findings(self):
        result = SubagentResult(
            findings=[{"summary": "Finding"}],
        )
        assert result.has_findings is True

    def test_subagent_result_has_errors(self):
        result = SubagentResult(
            errors=["Error 1"],
        )
        assert result.has_errors is True


class TestStateTransitions:
    def test_valid_transitions(self):
        assert is_valid_transition(SubagentStatus.CREATED, SubagentStatus.QUEUED) is True
        assert is_valid_transition(SubagentStatus.QUEUED, SubagentStatus.RUNNING) is True
        assert is_valid_transition(SubagentStatus.RUNNING, SubagentStatus.COMPLETED) is True
        assert is_valid_transition(SubagentStatus.RUNNING, SubagentStatus.FAILED) is True
        assert is_valid_transition(SubagentStatus.RUNNING, SubagentStatus.CANCELLED) is True

    def test_invalid_transitions(self):
        assert is_valid_transition(SubagentStatus.CREATED, SubagentStatus.RUNNING) is False
        assert is_valid_transition(SubagentStatus.COMPLETED, SubagentStatus.RUNNING) is False
        assert is_valid_transition(SubagentStatus.FAILED, SubagentStatus.COMPLETED) is False

    def test_terminal_states(self):
        assert is_valid_transition(SubagentStatus.COMPLETED, SubagentStatus.FAILED) is False
        assert is_valid_transition(SubagentStatus.CANCELLED, SubagentStatus.RUNNING) is False


class TestRoles:
    def test_get_researcher_role(self):
        role_def = get_role_definition(SubagentRole.RESEARCHER)
        assert role_def.role_id == SubagentRole.RESEARCHER
        assert "filesystem.write" in role_def.denied_capabilities

    def test_get_implementer_role(self):
        role_def = get_role_definition(SubagentRole.IMPLEMENTER)
        assert "filesystem.write" in role_def.default_capabilities
        assert "git.push" in role_def.denied_capabilities

    def test_get_tester_role(self):
        role_def = get_role_definition(SubagentRole.TESTER)
        assert "shell.execute" in role_def.default_capabilities

    def test_get_reviewer_role(self):
        role_def = get_role_definition(SubagentRole.REVIEWER)
        assert "filesystem.write" in role_def.denied_capabilities

    def test_get_debugger_role(self):
        role_def = get_role_definition(SubagentRole.DEBUGGER)
        assert "shell.execute" in role_def.default_capabilities


class TestBudget:
    def test_create_budget(self):
        budget = create_budget(SubagentRole.RESEARCHER)
        assert budget.max_model_calls == 20
        assert budget.max_tool_calls == 30

    def test_budget_with_overrides(self):
        budget = create_budget(SubagentRole.RESEARCHER, {"max_model_calls": 50})
        assert budget.max_model_calls == 50

    def test_budget_consumption(self):
        budget = SubagentBudget(max_model_calls=5)
        assert budget.consume_model_call() is True
        assert budget.model_calls == 1
        assert budget.remaining_model_calls == 4

    def test_budget_exhaustion(self):
        budget = SubagentBudget(max_model_calls=1)
        assert budget.consume_model_call() is True
        assert budget.consume_model_call() is False
        assert budget.is_exhausted is True

    def test_budget_exhausted_reason(self):
        budget = SubagentBudget(max_model_calls=1)
        budget.consume_model_call()
        assert "model_calls" in budget.exhausted_reason

    def test_budget_time_exhaustion(self):
        budget = SubagentBudget(max_time_seconds=0)
        assert budget.is_exhausted is True
        assert "time" in budget.exhausted_reason

    def test_derive_child_budget(self):
        parent = SubagentBudget(
            max_model_calls=20,
            max_tool_calls=30,
            max_child_agents=2,
        )
        child = derive_child_budget(parent, SubagentRole.RESEARCHER)
        assert child.max_model_calls <= parent.remaining_model_calls
        assert child.max_child_agents == 0

    def test_budget_usage_summary(self):
        budget = SubagentBudget(max_model_calls=10)
        budget.consume_model_call()
        summary = budget.usage_summary()
        assert "1/10" in summary["model_calls"]


class TestSubagentManager:
    def test_create_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )

        subagent = manager.create(task)
        assert subagent.id is not None
        assert manager.count == 1

    def test_get_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)

        retrieved = manager.get(str(subagent.id))
        assert retrieved is not None
        assert retrieved.id == subagent.id

    def test_list_subagents(self):
        manager = SubagentManager()
        for _ in range(3):
            task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
            manager.create(task)

        assert len(manager.list()) == 3

    def test_list_by_status(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)

        created = manager.list_by_status(SubagentStatus.CREATED)
        assert len(created) == 1

    def test_start_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)

        assert manager.start(str(subagent.id)) is True
        assert subagent.status == SubagentStatus.RUNNING

    def test_complete_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)
        manager.start(str(subagent.id))

        result = SubagentResult(subagent_id=str(subagent.id), summary="Done")
        assert manager.complete(str(subagent.id), result) is True
        assert subagent.status == SubagentStatus.COMPLETED

    def test_fail_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)
        manager.start(str(subagent.id))

        assert manager.fail(str(subagent.id), "Error") is True
        assert subagent.status == SubagentStatus.FAILED

    def test_cancel_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)

        assert manager.cancel(str(subagent.id)) is True
        assert subagent.status == SubagentStatus.CANCELLED

    def test_timeout_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)
        manager.start(str(subagent.id))

        assert manager.timeout(str(subagent.id)) is True
        assert subagent.status == SubagentStatus.TIMED_OUT

    def test_block_subagent(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)
        manager.start(str(subagent.id))

        assert manager.block(str(subagent.id), "Security") is True
        assert subagent.status == SubagentStatus.BLOCKED

    def test_invalid_transition(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)

        # Cannot complete from CREATED
        assert manager.complete(str(subagent.id)) is False

    def test_add_child(self):
        manager = SubagentManager()
        parent_task = SubagentTask(objective="Parent", role=SubagentRole.RESEARCHER)
        parent = manager.create(parent_task)

        child_task = SubagentTask(objective="Child", role=SubagentRole.RESEARCHER)
        child = manager.create(child_task, parent_id=str(parent.id))

        assert manager.add_child(str(parent.id), str(child.id)) is True
        assert str(child.id) in parent.child_ids

    def test_get_tree(self):
        manager = SubagentManager()
        parent_task = SubagentTask(objective="Parent", role=SubagentRole.RESEARCHER)
        parent = manager.create(parent_task)

        child_task = SubagentTask(objective="Child", role=SubagentRole.RESEARCHER)
        child = manager.create(child_task, parent_id=str(parent.id))
        manager.add_child(str(parent.id), str(child.id))

        tree = manager.get_tree(str(parent.id))
        assert tree["id"] == str(parent.id)
        assert len(tree["children"]) == 1

    def test_summary(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        manager.create(task)

        summary = manager.summary()
        assert summary["total"] == 1


class TestOrchestrator:
    def test_create_orchestrator(self):
        orch = create_orchestrator(max_concurrent=5)
        assert orch.manager is not None

    def test_delegate(self):
        orch = create_orchestrator()
        subagent = orch.delegate(
            objective="Test task",
            role=SubagentRole.RESEARCHER,
        )
        assert subagent.id is not None
        assert subagent.role == SubagentRole.RESEARCHER

    def test_delegate_with_parent(self):
        orch = create_orchestrator()
        parent = orch.delegate(
            objective="Parent task",
            role=SubagentRole.RESEARCHER,
        )

        child = orch.delegate(
            objective="Child task",
            role=SubagentRole.RESEARCHER,
            parent_id=str(parent.id),
        )
        assert child.parent_id == str(parent.id)

    def test_list_active(self):
        orch = create_orchestrator()
        subagent = orch.delegate(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )
        orch.start(str(subagent.id))

        active = orch.list_active()
        assert len(active) == 1

    def test_list_by_run(self):
        orch = create_orchestrator()
        subagent = orch.delegate(
            objective="Test",
            role=SubagentRole.RESEARCHER,
            parent_run_id="run-123",
        )

        run_subagents = orch.list_by_run("run-123")
        assert len(run_subagents) == 1

    def test_can_execute(self):
        orch = create_orchestrator(max_concurrent=1)
        assert orch.can_execute() is True

        subagent = orch.delegate(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )
        orch.start(str(subagent.id))

        assert orch.can_execute() is False

    def test_cancel(self):
        orch = create_orchestrator()
        subagent = orch.delegate(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )

        assert orch.cancel(str(subagent.id)) is True

    def test_summary(self):
        orch = create_orchestrator(max_concurrent=5)
        summary = orch.summary()
        assert summary["max_concurrent"] == 5


class TestDelegationContract:
    def test_create_contract(self):
        contract = create_contract(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )
        assert contract.objective == "Test"
        assert contract.role == SubagentRole.RESEARCHER

    def test_contract_has_role_defaults(self):
        contract = create_contract(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )
        assert len(contract.allowed_capabilities) > 0

    def test_contract_denied_capabilities(self):
        contract = create_contract(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )
        assert "filesystem.write" in contract.denied_capabilities


class TestSubagentContext:
    def test_create_context(self):
        context = create_context(
            objective="Test",
            role=SubagentRole.RESEARCHER,
            inputs={"key": "value"},
        )
        assert context.objective == "Test"
        assert context.inputs["key"] == "value"

    def test_working_memory(self):
        context = create_context(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )
        context.set_working_memory("finding", "value")
        assert context.get_working_memory("finding") == "value"

    def test_build_prompt_context(self):
        context = create_context(
            objective="Test",
            role=SubagentRole.RESEARCHER,
            inputs={"key": "value"},
        )
        prompt_ctx = context.build_prompt_context()
        assert prompt_ctx["objective"] == "Test"


class TestResultAggregator:
    def test_aggregate_empty(self):
        aggregator = ResultAggregator()
        result = aggregator.aggregate([])
        assert result.status == "no_results"

    def test_aggregate_single(self):
        aggregator = ResultAggregator()
        result = aggregator.aggregate([
            SubagentResult(
                subagent_id="test",
                status=SubagentStatus.COMPLETED,
                summary="Done",
            )
        ])
        assert result.status == "success"
        assert result.success_count == 1

    def test_aggregate_multiple(self):
        aggregator = ResultAggregator()
        result = aggregator.aggregate([
            SubagentResult(subagent_id="a", status=SubagentStatus.COMPLETED, summary="A"),
            SubagentResult(subagent_id="b", status=SubagentStatus.COMPLETED, summary="B"),
        ])
        assert result.status == "success"
        assert result.success_count == 2

    def test_aggregate_with_failures(self):
        aggregator = ResultAggregator()
        result = aggregator.aggregate([
            SubagentResult(subagent_id="a", status=SubagentStatus.COMPLETED, summary="A"),
            SubagentResult(subagent_id="b", status=SubagentStatus.FAILED, summary="B"),
        ])
        assert result.status == "failed"
        assert result.failure_count == 1

    def test_aggregate_conflicts(self):
        aggregator = ResultAggregator()
        result = aggregator.aggregate([
            SubagentResult(
                subagent_id="a",
                status=SubagentStatus.COMPLETED,
                findings=[{"topic": "bug", "conclusion": "X"}],
            ),
            SubagentResult(
                subagent_id="b",
                status=SubagentStatus.COMPLETED,
                findings=[{"topic": "bug", "conclusion": "Y"}],
            ),
        ])
        assert result.status == "conflicting"
        assert len(result.conflicts) > 0

    def test_confidence_calculation(self):
        aggregator = ResultAggregator()
        result = aggregator.aggregate([
            SubagentResult(subagent_id="a", status=SubagentStatus.COMPLETED),
            SubagentResult(subagent_id="b", status=SubagentStatus.COMPLETED),
        ])
        assert result.confidence == 1.0


class TestSecurityIntegration:
    def test_researcher_cannot_write(self):
        role_def = get_role_definition(SubagentRole.RESEARCHER)
        assert "filesystem.write" in role_def.denied_capabilities

    def test_researcher_cannot_execute_shell(self):
        role_def = get_role_definition(SubagentRole.RESEARCHER)
        assert "shell.execute" in role_def.denied_capabilities

    def test_implementer_cannot_push(self):
        role_def = get_role_definition(SubagentRole.IMPLEMENTER)
        assert "git.push" in role_def.denied_capabilities

    def test_subagent_blocked_on_security_deny(self):
        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)
        manager.start(str(subagent.id))

        # Simulate security denial
        assert manager.block(str(subagent.id), "Security denied") is True
        assert subagent.status == SubagentStatus.BLOCKED

    def test_budget_cannot_go_negative(self):
        budget = SubagentBudget(max_model_calls=1)
        budget.consume_model_call()
        assert budget.model_calls == 1
        assert budget.remaining_model_calls == 0
        assert budget.consume_model_call() is False


class TestBudgetIntegration:
    def test_budget_exhaustion_stops_execution(self):
        budget = SubagentBudget(max_iterations=2)
        assert budget.consume_iteration() is True
        assert budget.consume_iteration() is True
        assert budget.is_exhausted is True

    def test_child_budget_within_parent(self):
        parent = SubagentBudget(
            max_model_calls=20,
            max_tool_calls=30,
            max_child_agents=2,
        )
        # Consume some parent budget
        for _ in range(10):
            parent.consume_model_call()

        child = derive_child_budget(parent, SubagentRole.RESEARCHER)
        assert child.max_model_calls <= parent.remaining_model_calls
        assert child.max_child_agents == 0

    def test_no_unbounded_recursion(self):
        budget = create_budget(SubagentRole.RESEARCHER)
        assert budget.max_child_agents == 0


class TestEventIntegration:
    def test_lifecycle_events(self):
        manager = SubagentManager()
        events = []

        def handler(event_type, subagent, **kwargs):
            events.append(event_type)

        manager.add_event_handler(handler)

        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        subagent = manager.create(task)
        manager.start(str(subagent.id))
        manager.complete(str(subagent.id))

        assert "subagent.created" in events
        assert "subagent.running" in events
        assert "subagent.completed" in events

    def test_orchestrator_events(self):
        orch = create_orchestrator()
        events = []

        def handler(event_type, **kwargs):
            events.append(event_type)

        orch.add_event_handler(handler)

        subagent = orch.delegate(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )

        assert "subagent.delegated" in events


class TestEndToEnd:
    def test_full_delegation_flow(self):
        orch = create_orchestrator()

        # Delegate
        subagent = orch.delegate(
            objective="Research the authentication bug",
            role=SubagentRole.RESEARCHER,
            parent_run_id="run-123",
        )

        # Start (transitions CREATED -> QUEUED -> RUNNING)
        assert orch.start(str(subagent.id)) is True
        assert orch.get(str(subagent.id)).status == SubagentStatus.RUNNING

        # Complete the subagent
        result = SubagentResult(
            subagent_id=str(subagent.id),
            status=SubagentStatus.COMPLETED,
            summary="Research complete",
        )
        assert orch.manager.complete(str(subagent.id), result) is True

        # Check final state
        final = orch.get(str(subagent.id))
        assert final.status == SubagentStatus.COMPLETED

    def test_cancel_flow(self):
        orch = create_orchestrator()

        subagent = orch.delegate(
            objective="Test",
            role=SubagentRole.RESEARCHER,
        )

        assert orch.cancel(str(subagent.id)) is True
        assert orch.get(str(subagent.id)).status == SubagentStatus.CANCELLED

    def test_parallel_research(self):
        orch = create_orchestrator(max_concurrent=3)

        agents = []
        for i in range(3):
            agent = orch.delegate(
                objective=f"Research topic {i}",
                role=SubagentRole.RESEARCHER,
            )
            orch.start(str(agent.id))
            agents.append(agent)

        active = orch.list_active()
        assert len(active) == 3

    def test_conflict_detection(self):
        # Two agents writing to same file should be detected
        orch = create_orchestrator()

        agent1 = orch.delegate(
            objective="Fix auth.py",
            role=SubagentRole.IMPLEMENTER,
        )

        agent2 = orch.delegate(
            objective="Also fix auth.py",
            role=SubagentRole.IMPLEMENTER,
        )

        # In real implementation, conflict detection would happen here
        assert agent1.id != agent2.id


class TestReport:
    def test_format_subagents_text(self):
        from argus.subagents.report import format_subagents_text

        manager = SubagentManager()
        task = SubagentTask(objective="Test", role=SubagentRole.RESEARCHER)
        manager.create(task)

        text = format_subagents_text(manager.list())
        assert "SUBAGENTS" in text

    def test_format_empty_subagents(self):
        from argus.subagents.report import format_subagents_text

        text = format_subagents_text([])
        assert "No subagents" in text

    def test_summarize_results(self):
        from argus.subagents.result import summarize_results

        results = [
            SubagentResult(subagent_id="a", status=SubagentStatus.COMPLETED),
            SubagentResult(subagent_id="b", status=SubagentStatus.FAILED),
        ]

        summary = summarize_results(results)
        assert summary["count"] == 2
        assert summary["success_rate"] == 0.5
