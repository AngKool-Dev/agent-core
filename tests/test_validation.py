"""Tests for the ARGUS validation package."""

import os
import tempfile
import pytest
from unittest.mock import MagicMock

from argus.validation import (
    ContractViolation,
    OutcomeType,
    ToolCallRecord,
    ValidationCategory,
    ValidationConfig,
    ValidationConstraint,
    ValidationResult,
    ValidationRun,
    ValidationScenario,
    ValidationStatus,
    ValidationTier,
    create_default_contract,
    create_lenient_contract,
    create_strict_contract,
    evaluate_validation_run,
    generate_validation_report,
    get_all_scenarios,
    get_scenario_by_id,
    get_scenarios_by_category,
    get_scenarios_by_tier,
    run_single_scenario,
    run_validation,
    scenario_a_file_creation,
    scenario_b_debugging,
    scenario_c_refactoring,
    scenario_d_testing,
    scenario_e_git_workflow,
    scenario_f_dependency_management,
    scenario_g_security_review,
    scenario_h_multi_step_reasoning,
    scenario_i_documentation,
    scenario_j_recovery_task,
    ScenarioVerifier,
    ValidationEvaluator,
    ValidationReporter,
    ValidationRunner,
)


class TestValidationModels:
    """Tests for validation data models."""

    def test_validation_scenario_creation(self):
        scenario = scenario_a_file_creation()
        assert scenario.scenario_id == "val-a-file-creation"
        assert scenario.name == "Python Module Creation"
        assert scenario.category == ValidationCategory.FILE_MANIPULATION
        assert scenario.tier == ValidationTier.TIER_1
        assert len(scenario.success_criteria) > 0

    def test_validation_scenario_to_dict(self):
        scenario = scenario_a_file_creation()
        data = scenario.to_dict()
        assert data["scenario_id"] == "val-a-file-creation"
        assert data["category"] == "file_manipulation"
        assert data["tier"] == "tier_1"

    def test_validation_result_creation(self):
        result = ValidationResult(scenario_id="test-scenario")
        assert result.status == ValidationStatus.PENDING
        assert result.outcome == OutcomeType.FAILURE
        assert result.tool_call_count == 0

    def test_validation_result_tool_calls(self):
        result = ValidationResult(
            scenario_id="test",
            tool_calls=[
                ToolCallRecord(tool_name="read", arguments={"file": "test.py"}, success=True),
                ToolCallRecord(tool_name="write", arguments={"file": "out.py"}, success=False),
            ],
        )
        assert result.tool_call_count == 2
        assert result.successful_tool_calls == 1
        assert result.failed_tool_calls == 1

    def test_validation_result_to_dict(self):
        result = ValidationResult(scenario_id="test")
        data = result.to_dict()
        assert data["scenario_id"] == "test"
        assert data["status"] == "pending"
        assert data["outcome"] == "failure"

    def test_validation_run_creation(self):
        run = ValidationRun(total_scenarios=10)
        assert run.total_scenarios == 10
        assert run.success_rate == 0.0

    def test_validation_run_success_rate(self):
        run = ValidationRun(total_scenarios=4, passed=3, failed=1)
        assert run.success_rate == 0.75

    def test_validation_run_to_dict(self):
        run = ValidationRun(total_scenarios=2, passed=1, failed=1)
        data = run.to_dict()
        assert data["total_scenarios"] == 2
        assert data["success_rate"] == 0.5

    def test_validation_config_defaults(self):
        config = ValidationConfig()
        assert config.timeout_seconds == 300
        assert config.enable_security_checks is True
        assert config.enable_verification is True
        assert config.enable_contract_enforcement is True


class TestValidationScenarios:
    """Tests for validation scenarios."""

    def test_all_scenarios_present(self):
        scenarios = get_all_scenarios()
        assert len(scenarios) == 10

    def test_scenario_ids_unique(self):
        scenarios = get_all_scenarios()
        ids = [s.scenario_id for s in scenarios]
        assert len(ids) == len(set(ids))

    def test_scenario_a_file_creation(self):
        scenario = scenario_a_file_creation()
        assert scenario.scenario_id == "val-a-file-creation"
        assert "calculator.py" in scenario.expected_files

    def test_scenario_b_debugging(self):
        scenario = scenario_b_debugging()
        assert scenario.scenario_id == "val-b-debugging"
        assert "broken_sort.py" in scenario.initial_state

    def test_scenario_c_refactoring(self):
        scenario = scenario_c_refactoring()
        assert scenario.scenario_id == "val-c-refactoring"
        assert "data_processor.py" in scenario.initial_state

    def test_scenario_d_testing(self):
        scenario = scenario_d_testing()
        assert scenario.scenario_id == "val-d-testing"
        assert "test_string_utils.py" in scenario.expected_files

    def test_scenario_e_git_workflow(self):
        scenario = scenario_e_git_workflow()
        assert scenario.scenario_id == "val-e-git-workflow"
        assert ".git" in scenario.expected_files

    def test_scenario_f_dependency_management(self):
        scenario = scenario_f_dependency_management()
        assert scenario.scenario_id == "val-f-dependency-management"
        assert "requirements.txt" in scenario.expected_files

    def test_scenario_g_security_review(self):
        scenario = scenario_g_security_review()
        assert scenario.scenario_id == "val-g-security-review"
        assert "auth.py" in scenario.initial_state

    def test_scenario_h_multi_step_reasoning(self):
        scenario = scenario_h_multi_step_reasoning()
        assert scenario.scenario_id == "val-h-multi-step-reasoning"
        assert len(scenario.expected_files) == 3

    def test_scenario_i_documentation(self):
        scenario = scenario_i_documentation()
        assert scenario.scenario_id == "val-i-documentation"
        assert "README.md" in scenario.expected_files

    def test_scenario_j_recovery_task(self):
        scenario = scenario_j_recovery_task()
        assert scenario.scenario_id == "val-j-recovery-task"
        assert "input.csv" in scenario.initial_state

    def test_get_scenario_by_id(self):
        scenario = get_scenario_by_id("val-a-file-creation")
        assert scenario is not None
        assert scenario.name == "Python Module Creation"

    def test_get_scenario_by_id_not_found(self):
        scenario = get_scenario_by_id("nonexistent")
        assert scenario is None

    def test_get_scenarios_by_tier(self):
        tier1 = get_scenarios_by_tier(ValidationTier.TIER_1)
        assert len(tier1) >= 1
        assert all(s.tier == ValidationTier.TIER_1 for s in tier1)

    def test_get_scenarios_by_category(self):
        file_scenarios = get_scenarios_by_category(ValidationCategory.FILE_MANIPULATION)
        assert len(file_scenarios) >= 1
        assert all(s.category == ValidationCategory.FILE_MANIPULATION for s in file_scenarios)


class TestOutcomeContract:
    """Tests for the Real Agent Outcome Contract."""

    def test_default_contract_creation(self):
        contract = create_default_contract()
        assert len(contract.clauses) >= 5
        assert contract.name == "Real Agent Outcome Contract"

    def test_lenient_contract_creation(self):
        contract = create_lenient_contract()
        assert len(contract.clauses) == 2

    def test_strict_contract_creation(self):
        contract = create_strict_contract()
        assert all(c.required for c in contract.clauses)

    def test_contract_evaluate_success(self):
        contract = create_default_contract()
        result = ValidationResult(
            scenario_id="test",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
            output="Task completed successfully",
            tool_calls=[
                ToolCallRecord(tool_name="read", arguments={}, success=True),
                ToolCallRecord(tool_name="write", arguments={}, success=True),
            ],
        )
        violations = contract.evaluate(result)
        # Should have minimal violations for a good result
        assert ContractViolation.OUTPUT_FORMAT not in violations
        assert ContractViolation.TOOL_USAGE not in violations

    def test_contract_evaluate_failure(self):
        contract = create_default_contract()
        result = ValidationResult(
            scenario_id="test",
            status=ValidationStatus.FAILED,
            outcome=OutcomeType.FAILURE,
            output="",
            tool_calls=[],
        )
        violations = contract.evaluate(result)
        assert ContractViolation.OUTPUT_FORMAT in violations
        assert ContractViolation.TOOL_USAGE in violations

    def test_contract_evaluate_timeout(self):
        contract = create_default_contract()
        result = ValidationResult(
            scenario_id="test",
            status=ValidationStatus.TIMED_OUT,
            outcome=OutcomeType.TIMEOUT,
            output="Partial output",
            tool_calls=[ToolCallRecord(tool_name="read", arguments={}, success=True)],
        )
        violations = contract.evaluate(result)
        assert ContractViolation.TIMEOUT in violations


class TestScenarioVerifier:
    """Tests for the scenario verifier."""

    def test_verify_success(self):
        verifier = ScenarioVerifier()
        scenario = scenario_a_file_creation()
        result = ValidationResult(
            scenario_id=scenario.scenario_id,
            status=ValidationStatus.RUNNING,
            files_created=["calculator.py"],
            output="Created calculator.py",
            tool_calls=[ToolCallRecord(tool_name="write", arguments={}, success=True)],
        )
        verified = verifier.verify(scenario, result)
        assert verified.status in (ValidationStatus.PASSED, ValidationStatus.FAILED)
        assert len(verified.verification_results) > 0

    def test_verify_failure(self):
        verifier = ScenarioVerifier()
        scenario = scenario_a_file_creation()
        result = ValidationResult(
            scenario_id=scenario.scenario_id,
            status=ValidationStatus.RUNNING,
            files_created=[],
            output="",
            errors=["Failed to create file"],
        )
        verified = verifier.verify(scenario, result)
        assert verified.status == ValidationStatus.FAILED

    def test_verify_file_exists(self):
        verifier = ScenarioVerifier()
        scenario = scenario_a_file_creation()
        result = ValidationResult(
            scenario_id=scenario.scenario_id,
            files_created=["calculator.py"],
        )
        passed = verifier._check_file_exists("", scenario, result)
        assert passed is True

    def test_verify_file_not_exists(self):
        verifier = ScenarioVerifier()
        scenario = scenario_a_file_creation()
        result = ValidationResult(
            scenario_id=scenario.scenario_id,
            files_created=[],
        )
        passed = verifier._check_file_exists("", scenario, result)
        assert passed is False


class TestValidationRunner:
    """Tests for the validation runner."""

    def test_run_scenario_with_callback(self):
        runner = ValidationRunner()
        scenario = scenario_a_file_creation()

        def mock_callback(prompt, initial_state):
            return {
                "output": "Created calculator.py",
                "tool_calls": [
                    {"tool": "write", "arguments": {"file": "calculator.py"}, "success": True}
                ],
                "files_created": ["calculator.py"],
                "files_modified": [],
                "files_deleted": [],
                "errors": [],
            }

        result = runner.run_scenario(scenario, mock_callback)
        assert result.scenario_id == scenario.scenario_id
        assert result.status in (
            ValidationStatus.PASSED,
            ValidationStatus.FAILED,
            ValidationStatus.ERROR,
        )
        assert result.duration_seconds >= 0

    def test_run_scenario_without_callback(self):
        runner = ValidationRunner()
        scenario = scenario_a_file_creation()
        result = runner.run_scenario(scenario)
        assert result.scenario_id == scenario.scenario_id

    def test_run_all_scenarios(self):
        runner = ValidationRunner()
        run = runner.run_all()
        assert run.total_scenarios == 10
        assert len(run.scenario_results) == 10

    def test_run_with_config_filter(self):
        config = ValidationConfig(scenario_ids=["val-a-file-creation"])
        runner = ValidationRunner(config)
        run = runner.run_all()
        assert run.total_scenarios == 1
        assert "val-a-file-creation" in run.scenario_results


class TestValidationEvaluator:
    """Tests for the validation evaluator."""

    def test_evaluate_run(self):
        evaluator = ValidationEvaluator()
        run = ValidationRun(total_scenarios=2, passed=1, failed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        run.scenario_results["test-2"] = ValidationResult(
            scenario_id="test-2",
            status=ValidationStatus.FAILED,
            outcome=OutcomeType.FAILURE,
        )
        evaluation = evaluator.evaluate_run(run)
        assert evaluation["summary"]["total"] == 2
        assert evaluation["summary"]["pass_rate"] == 0.5

    def test_evaluate_empty_run(self):
        evaluator = ValidationEvaluator()
        run = ValidationRun(total_scenarios=0)
        evaluation = evaluator.evaluate_run(run)
        assert evaluation["summary"]["total"] == 0
        assert evaluation["summary"]["pass_rate"] == 0.0

    def test_generate_recommendations_low_pass_rate(self):
        evaluator = ValidationEvaluator()
        run = ValidationRun(total_scenarios=10, passed=3, failed=7)
        recommendations = evaluator._generate_recommendations(run)
        assert any("CRITICAL" in r or "below" in r for r in recommendations)

    def test_generate_recommendations_high_pass_rate(self):
        evaluator = ValidationEvaluator()
        run = ValidationRun(total_scenarios=10, passed=10)
        recommendations = evaluator._generate_recommendations(run)
        assert any("passed" in r.lower() for r in recommendations)

    def test_compare_runs(self):
        evaluator = ValidationEvaluator()
        run1 = ValidationRun(total_scenarios=10, passed=8)
        run2 = ValidationRun(total_scenarios=10, passed=6)
        comparison = evaluator.compare_runs(run1, run2)
        assert comparison["pass_rate_delta"] == pytest.approx(0.2)
        assert comparison["passed_delta"] == 2


class TestValidationReporter:
    """Tests for the validation reporter."""

    def test_generate_text_report(self):
        reporter = ValidationReporter()
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
            output="Success",
        )
        report = reporter.generate_text_report(run)
        assert "ARGUS VALIDATION REPORT" in report
        assert "PASS" in report

    def test_generate_markdown_report(self):
        reporter = ValidationReporter()
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        report = reporter.generate_markdown_report(run)
        assert "# ARGUS Validation Report" in report
        assert "| Scenario |" in report

    def test_generate_json_report(self):
        reporter = ValidationReporter()
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        report = reporter.generate_json_report(run)
        assert "run_id" in report
        assert "evaluation" in report

    def test_generate_report_with_failures(self):
        reporter = ValidationReporter()
        run = ValidationRun(total_scenarios=1, failed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.FAILED,
            outcome=OutcomeType.FAILURE,
            errors=["Something went wrong"],
        )
        report = reporter.generate_text_report(run)
        assert "FAIL" in report
        assert "FAILURE DETAILS" in report


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_run_validation(self):
        run = run_validation()
        assert run.total_scenarios == 10

    def test_run_single_scenario(self):
        result = run_single_scenario("val-a-file-creation")
        assert result is not None
        assert result.scenario_id == "val-a-file-creation"

    def test_run_single_scenario_not_found(self):
        result = run_single_scenario("nonexistent")
        assert result is None

    def test_evaluate_validation_run(self):
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        evaluation = evaluate_validation_run(run)
        assert "summary" in evaluation
        assert "recommendations" in evaluation

    def test_generate_validation_report_text(self):
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        report = generate_validation_report(run, "text")
        assert "ARGUS VALIDATION REPORT" in report

    def test_generate_validation_report_markdown(self):
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        report = generate_validation_report(run, "markdown")
        assert "# ARGUS Validation Report" in report

    def test_generate_validation_report_json(self):
        run = ValidationRun(total_scenarios=1, passed=1)
        run.scenario_results["test-1"] = ValidationResult(
            scenario_id="test-1",
            status=ValidationStatus.PASSED,
            outcome=OutcomeType.SUCCESS,
        )
        report = generate_validation_report(run, "json")
        assert '"run_id"' in report
