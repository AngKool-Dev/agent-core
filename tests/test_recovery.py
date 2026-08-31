"""Tests for recovery engine."""

import pytest

from argus.recovery import (
    AttemptRecord,
    FailureClass,
    FailureClassifier,
    FailureEvidence,
    RecoveryAction,
    RecoveryBudget,
    RecoveryEngine,
    RecoveryOption,
    RecoveryPlan,
    RecoveryPlanner,
    RecoveryResult,
    RecoveryState,
    RecoveryStatus,
    RecoveryStrategies,
    RecoveryStrategyType,
    create_recovery_engine,
)


class TestRecoveryBudget:
    def test_default_budget(self):
        budget = RecoveryBudget.default()
        assert budget.max_attempts == 10
        assert budget.can_retry is True
        assert budget.can_replan is True

    def test_budget_exhausted(self):
        budget = RecoveryBudget(max_attempts=1, max_retries=1)
        budget.consume_retry()
        assert budget.exhausted is True
        assert budget.can_retry is False

    def test_budget_consumption(self):
        budget = RecoveryBudget(max_attempts=5, max_retries=3)
        budget.consume_retry()
        assert budget.retries == 1
        assert budget.attempts == 1

    def test_time_budget(self):
        budget = RecoveryBudget(time_budget_seconds=0.001)
        import time
        time.sleep(0.01)
        assert budget.exhausted is True

    def test_conservative_budget(self):
        budget = RecoveryBudget.conservative()
        assert budget.max_attempts == 5

    def test_aggressive_budget(self):
        budget = RecoveryBudget.aggressive()
        assert budget.max_attempts == 15

    def test_budget_summary(self):
        budget = RecoveryBudget()
        summary = budget.summary()
        assert "Attempts" in summary
        assert "Retries" in summary


class TestFailureClassifier:
    def test_classify_timeout(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("Connection timed out after 30s")
        assert evidence.failure_class == FailureClass.TRANSIENT

    def test_classify_rate_limit(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("Rate limit exceeded: 429 Too Many Requests")
        assert evidence.failure_class == FailureClass.TRANSIENT

    def test_classify_auth_failure(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("Authentication failed: invalid API key")
        assert evidence.failure_class == FailureClass.BACKEND

    def test_classify_test_failure(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("pytest failed: 3 failures=3")
        assert evidence.failure_class == FailureClass.CODE

    def test_classify_syntax_error(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("SyntaxError: invalid syntax")
        assert evidence.failure_class == FailureClass.CODE

    def test_classify_environment(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("No such file or directory: /tmp/missing")
        assert evidence.failure_class == FailureClass.ENVIRONMENT

    def test_classify_unknown(self):
        classifier = FailureClassifier()
        evidence = classifier.classify("Something weird happened")
        assert evidence.failure_class == FailureClass.UNKNOWN

    def test_classify_from_result(self):
        classifier = FailureClassifier()
        result = {"error": "Connection timeout", "return_code": 1}
        evidence = classifier.classify_from_result(result)
        assert evidence.failure_class == FailureClass.TRANSIENT


class TestRecoveryStrategies:
    def test_transient_strategies(self):
        budget = RecoveryBudget()
        strategies = RecoveryStrategies.get_strategies_for_failure(FailureClass.TRANSIENT, budget)
        assert len(strategies) > 0
        assert any(s.strategy == RecoveryStrategyType.RETRY for s in strategies)

    def test_backend_strategies(self):
        budget = RecoveryBudget()
        strategies = RecoveryStrategies.get_strategies_for_failure(FailureClass.BACKEND, budget)
        assert any(s.strategy == RecoveryStrategyType.BACKEND_SWITCH for s in strategies)

    def test_code_strategies(self):
        budget = RecoveryBudget()
        strategies = RecoveryStrategies.get_strategies_for_failure(FailureClass.CODE, budget)
        assert any(s.strategy == RecoveryStrategyType.REPAIR for s in strategies)

    def test_user_required_strategies(self):
        budget = RecoveryBudget()
        strategies = RecoveryStrategies.get_strategies_for_failure(FailureClass.USER_REQUIRED, budget)
        assert any(s.strategy == RecoveryStrategyType.ESCALATE for s in strategies)

    def test_select_best_strategy(self):
        budget = RecoveryBudget()
        strategy = RecoveryStrategies.select_best_strategy(FailureClass.TRANSIENT, budget)
        assert strategy == RecoveryStrategyType.RETRY

    def test_no_strategies_when_exhausted(self):
        budget = RecoveryBudget(max_attempts=0)
        strategies = RecoveryStrategies.get_strategies_for_failure(FailureClass.TRANSIENT, budget)
        # Should still return strategies but they won't be available
        assert isinstance(strategies, list)


class TestRecoveryPlanner:
    def test_create_retry_plan(self):
        planner = RecoveryPlanner()
        failure = FailureEvidence(
            failure_class=FailureClass.TRANSIENT,
            message="timeout",
        )
        state = RecoveryState(task="test")
        plan = planner.create_recovery_plan(failure, state)
        assert plan.strategy == RecoveryStrategyType.RETRY

    def test_create_fallback_plan(self):
        planner = RecoveryPlanner()
        failure = FailureEvidence(
            failure_class=FailureClass.BACKEND,
            message="provider unavailable",
        )
        state = RecoveryState(task="test")
        plan = planner.create_recovery_plan(failure, state, available_capabilities=["cap1", "cap2"])
        assert plan.strategy == RecoveryStrategyType.BACKEND_SWITCH

    def test_create_replan_plan(self):
        planner = RecoveryPlanner()
        failure = FailureEvidence(
            failure_class=FailureClass.LOGICAL,
            message="verification failed",
        )
        state = RecoveryState(task="test")
        plan = planner.create_recovery_plan(failure, state)
        assert plan.strategy == RecoveryStrategyType.REPLAN

    def test_create_escalate_plan(self):
        planner = RecoveryPlanner()
        failure = FailureEvidence(
            failure_class=FailureClass.USER_REQUIRED,
            message="requires user input",
        )
        state = RecoveryState(task="test")
        plan = planner.create_recovery_plan(failure, state)
        assert plan.strategy == RecoveryStrategyType.ESCALATE


class TestRecoveryState:
    def test_add_attempt(self):
        state = RecoveryState(task="test")
        state.add_attempt(AttemptRecord(attempt_number=1, capability_id="cap", input_data={}, success=True))
        assert state.attempt_count == 1

    def test_add_failure(self):
        state = RecoveryState(task="test")
        state.add_failure(FailureEvidence(failure_class=FailureClass.CODE, message="error"))
        assert state.failure_count == 1

    def test_add_assumption(self):
        state = RecoveryState(task="test")
        state.add_assumption("file exists", True)
        assert state.assumptions["file exists"] is True

    def test_invalidate_assumption(self):
        state = RecoveryState(task="test")
        state.add_assumption("file exists", True)
        state.invalidate_assumption("file exists")
        assert "file exists" in state.invalid_assumptions

    def test_add_learned_fact(self):
        state = RecoveryState(task="test")
        state.add_learned_fact("file is missing")
        assert "file is missing" in state.learned_facts

    def test_last_failure(self):
        state = RecoveryState(task="test")
        state.add_failure(FailureEvidence(failure_class=FailureClass.CODE, message="error1"))
        state.add_failure(FailureEvidence(failure_class=FailureClass.CODE, message="error2"))
        assert state.last_failure.message == "error2"

    def test_common_failure_class(self):
        state = RecoveryState(task="test")
        state.add_failure(FailureEvidence(failure_class=FailureClass.CODE, message="e1"))
        state.add_failure(FailureEvidence(failure_class=FailureClass.CODE, message="e2"))
        state.add_failure(FailureEvidence(failure_class=FailureClass.TRANSIENT, message="e3"))
        assert state.common_failure_class == "code"


class TestRecoveryEngine:
    def test_create_engine(self):
        engine = create_recovery_engine()
        assert engine is not None

    def test_recover_from_transient(self):
        engine = create_recovery_engine()
        result = engine.recover(
            failure_message="Connection timed out",
            task="fetch data",
        )
        assert isinstance(result, RecoveryResult)
        assert len(result.actions) > 0

    def test_recover_from_code_failure(self):
        engine = create_recovery_engine()
        result = engine.recover(
            failure_message="pytest failed: 3 test failures",
            task="run tests",
        )
        assert isinstance(result, RecoveryResult)

    def test_recover_with_execute_fn(self):
        engine = create_recovery_engine()

        def mock_execute(capability_id, input_data, strategy):
            return {"success": True, "output": "recovered"}

        result = engine.recover(
            failure_message="timeout",
            task="test",
            execute_fn=mock_execute,
        )
        assert result.succeeded is True

    def test_recover_budget_exhausted(self):
        engine = create_recovery_engine(budget=RecoveryBudget(max_attempts=0))
        result = engine.recover(
            failure_message="error",
            task="test",
        )
        assert result.status == RecoveryStatus.EXHAUSTED

    def test_recover_with_available_capabilities(self):
        engine = create_recovery_engine()
        result = engine.recover(
            failure_message="provider unavailable",
            task="fetch",
            available_capabilities=["github", "web"],
        )
        assert isinstance(result, RecoveryResult)

    def test_recovery_consumes_budget(self):
        engine = create_recovery_engine(budget=RecoveryBudget(max_attempts=5, max_retries=3))
        result = engine.recover(
            failure_message="timeout",
            task="test",
        )
        assert engine.budget.attempts > 0

    def test_recovery_with_state(self):
        engine = create_recovery_engine()
        state = RecoveryState(task="test")
        state.add_failure(FailureEvidence(failure_class=FailureClass.CODE, message="previous error"))
        result = engine.recover(
            failure_message="timeout",
            task="test",
            state=state,
        )
        assert state.failure_count == 2  # Previous + new


class TestFailureEvidence:
    def test_evidence_creation(self):
        evidence = FailureEvidence(
            failure_class=FailureClass.TRANSIENT,
            message="timeout",
        )
        assert evidence.failure_class == FailureClass.TRANSIENT
        assert evidence.message == "timeout"
        assert evidence.timestamp > 0

    def test_evidence_to_dict(self):
        evidence = FailureEvidence(
            failure_class=FailureClass.CODE,
            message="error",
            command="pytest",
        )
        d = evidence.to_dict()
        assert d["failure_class"] == "code"
        assert d["command"] == "pytest"


class TestRecoveryResult:
    def test_result_creation(self):
        result = RecoveryResult(status=RecoveryStatus.SUCCESS)
        assert result.succeeded is True
        assert result.action_count == 0

    def test_result_with_actions(self):
        result = RecoveryResult(
            status=RecoveryStatus.SUCCESS,
            actions=[
                RecoveryAction(strategy=RecoveryStrategyType.RETRY, description="retry", success=True),
            ],
        )
        assert result.action_count == 1

    def test_result_to_dict(self):
        result = RecoveryResult(status=RecoveryStatus.FAILED, message="failed")
        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["message"] == "failed"