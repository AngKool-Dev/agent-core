"""Tests for the ARGUS production reality package."""

import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from argus.reality import (
    EnvironmentInfo,
    FailureCategory,
    InvariantId,
    InvariantResult,
    MCPCheckResult,
    ProviderAvailability,
    ProviderCheckResult,
    RealityRun,
    RealityScenarioResult,
    RealityStatus,
    ReleaseDecision,
    SecretCanaryResult,
    SubprocessCheckResult,
    WindowsCheckResult,
    capture_environment,
    get_safe_summary,
    validate_providers,
    validate_mcp,
    test_subprocess_reality,
    test_windows_hardening,
    run_secret_audit,
    run_invariant_tests,
    run_reality_scenarios,
    run_reality_suite,
    evaluate_reality_run,
    generate_reality_report,
    ProductionEnvironment,
    RealProviderValidator,
    RealMCPValidator,
    SubprocessRealityTester,
    WindowsHardeningTester,
    SecretSafetyAuditor,
    InvariantTester,
    RealityScenarioRunner,
    RealityRunner,
    RealityEvaluator,
    RealityReporter,
)


class TestRealityModels:
    """Tests for reality data models."""

    def test_environment_info_creation(self):
        info = EnvironmentInfo()
        assert info.python_version == ""
        assert info.os_name == ""

    def test_environment_info_to_dict(self):
        info = EnvironmentInfo(python_version="3.12.0", os_name="Windows")
        data = info.to_dict()
        assert data["python_version"] == "3.12.0"
        assert data["os_name"] == "Windows"

    def test_provider_check_result(self):
        result = ProviderCheckResult(
            provider_name="test",
            availability=ProviderAvailability.AVAILABLE,
        )
        assert result.availability == ProviderAvailability.AVAILABLE
        data = result.to_dict()
        assert data["provider_name"] == "test"

    def test_mcp_check_result(self):
        result = MCPCheckResult(
            server_name="test",
            status=RealityStatus.PASSED,
        )
        assert result.status == RealityStatus.PASSED

    def test_subprocess_check_result(self):
        result = SubprocessCheckResult(
            command="echo test",
            status=RealityStatus.PASSED,
            exit_code=0,
        )
        assert result.exit_code == 0

    def test_windows_check_result(self):
        result = WindowsCheckResult(
            check_name="test",
            status=RealityStatus.PASSED,
        )
        assert result.security_scope_maintained is True

    def test_secret_canary_result(self):
        result = SecretCanaryResult(artifact_name="test")
        assert result.canary_detected is False
        assert result.redaction_effective is True

    def test_invariant_result(self):
        result = InvariantResult(
            invariant_id=InvariantId.REAL_001,
            description="Test invariant",
            passed=True,
        )
        assert result.passed is True

    def test_reality_scenario_result(self):
        result = RealityScenarioResult(
            scenario_id="test",
            status=RealityStatus.PASSED,
        )
        assert result.status == RealityStatus.PASSED

    def test_reality_run_creation(self):
        run = RealityRun(total_checks=10, passed=8, failed=2)
        assert run.pass_rate == 0.8

    def test_release_decision(self):
        decision = ReleaseDecision(decision="QUALIFIED", version="1.0.0")
        assert decision.decision == "QUALIFIED"


class TestProductionEnvironment:
    """Tests for production environment capture."""

    def test_snapshot(self):
        env = ProductionEnvironment()
        info = env.snapshot()
        assert info.python_version != ""
        assert info.os_name != ""

    def test_to_dict(self):
        env = ProductionEnvironment()
        env.snapshot()
        data = env.to_dict()
        assert "python_version" in data
        assert "os_name" in data

    def test_safe_summary(self):
        env = ProductionEnvironment()
        summary = env.safe_summary()
        assert "Production Environment Summary" in summary

    def test_capture_environment(self):
        info = capture_environment()
        assert info.python_version != ""

    def test_get_safe_summary(self):
        summary = get_safe_summary()
        assert "Python:" in summary

    def test_no_secrets_in_env_vars(self):
        """Verify that secret environment variables are not captured."""
        # Set a secret-like variable
        os.environ["TEST_SECRET_KEY"] = "super_secret_value"
        try:
            env = ProductionEnvironment()
            info = env.snapshot()
            # Secret variable should not be in captured env vars
            assert "TEST_SECRET_KEY" not in info.environment_variables
        finally:
            del os.environ["TEST_SECRET_KEY"]


class TestRealProviderValidator:
    """Tests for real provider validation."""

    def test_validate_all(self):
        validator = RealProviderValidator()
        results = validator.validate_all()
        assert isinstance(results, dict)

    def test_validate_provider(self):
        validator = RealProviderValidator()
        result = validator.validate_provider("ollama")
        assert isinstance(result, ProviderCheckResult)

    def test_check_discovery(self):
        validator = RealProviderValidator()
        result = validator._check_discovery("ollama")
        assert isinstance(result, ProviderCheckResult)

    def test_check_configuration(self):
        validator = RealProviderValidator()
        result = validator._check_configuration("ollama")
        assert isinstance(result, ProviderCheckResult)

    def test_check_health(self):
        validator = RealProviderValidator()
        result = validator._check_health("ollama")
        assert isinstance(result, ProviderCheckResult)


class TestRealMCPValidator:
    """Tests for real MCP validation."""

    def test_validate_all(self):
        validator = RealMCPValidator()
        results = validator.validate_all()
        assert isinstance(results, dict)

    def test_server_start(self):
        validator = RealMCPValidator()
        # Server start is tested as part of validate_all
        results = validator.validate_all()
        assert "server_start" in results

    @pytest.mark.skip(reason="MCP subprocess tests are complex and may hang in CI")
    def test_full_mcp_lifecycle(self):
        """Full MCP lifecycle test - skipped by default."""
        validator = RealMCPValidator()
        results = validator.validate_all()
        assert len(results) > 1


class TestSubprocessRealityTester:
    """Tests for subprocess reality testing."""

    def test_run_all_tests(self):
        tester = SubprocessRealityTester()
        results = tester.run_all_tests()
        assert isinstance(results, dict)
        assert len(results) > 0

    def test_process_launch(self):
        tester = SubprocessRealityTester()
        tester._test_process_launch()
        assert "process_launch" in tester.results

    def test_stdout_capture(self):
        tester = SubprocessRealityTester()
        tester._test_stdout_capture()
        result = tester.results["stdout_capture"]
        assert result.stdout_captured is True

    def test_stderr_capture(self):
        tester = SubprocessRealityTester()
        tester._test_stderr_capture()
        result = tester.results["stderr_capture"]
        assert result.stderr_captured is True

    def test_exit_code(self):
        tester = SubprocessRealityTester()
        tester._test_exit_code()
        result = tester.results["exit_code"]
        assert result.exit_code == 42

    def test_timeout(self):
        tester = SubprocessRealityTester()
        tester._test_timeout()
        result = tester.results["timeout"]
        assert result.timed_out is True

    def test_cancellation(self):
        tester = SubprocessRealityTester()
        tester._test_cancellation()
        result = tester.results["cancellation"]
        assert result.cancelled is True

    def test_unicode_output(self):
        tester = SubprocessRealityTester()
        tester._test_unicode_output()
        result = tester.results["unicode_output"]
        assert result.status == RealityStatus.PASSED


class TestWindowsHardeningTester:
    """Tests for Windows hardening."""

    def test_run_all_tests(self):
        tester = WindowsHardeningTester()
        results = tester.run_all_tests()
        assert isinstance(results, dict)

    def test_platform_check(self):
        tester = WindowsHardeningTester()
        results = tester.run_all_tests()
        if os.name != "nt":
            assert "platform_check" in results
            assert results["platform_check"].status == RealityStatus.SKIPPED


class TestSecretSafetyAuditor:
    """Tests for secret safety audit."""

    def test_run_full_audit(self):
        auditor = SecretSafetyAuditor()
        results = auditor.run_full_audit()
        assert isinstance(results, dict)
        assert len(results) > 0

    def test_check_artifact(self):
        auditor = SecretSafetyAuditor()
        result = auditor._check_artifact("test", "clean content")
        assert result.canary_detected is False

    def test_check_artifact_with_canary(self):
        auditor = SecretSafetyAuditor()
        result = auditor._check_artifact("test", "ARGUS_SECRET_CANARY_DO_NOT_LEAK_123456")
        assert result.canary_detected is True
        assert result.status == RealityStatus.FAILED

    def test_canary_found_anywhere(self):
        auditor = SecretSafetyAuditor()
        auditor.run_full_audit()
        # Should be a boolean
        assert isinstance(auditor.canary_found_anywhere, bool)


class TestInvariantTester:
    """Tests for invariant testing."""

    def test_run_all_tests(self):
        tester = InvariantTester()
        results = tester.run_all_tests()
        assert isinstance(results, dict)
        assert len(results) == 30

    def test_all_invariants_present(self):
        tester = InvariantTester()
        results = tester.run_all_tests()
        for i in range(1, 31):
            name = f"REAL-{i:03d}"
            assert name in results

    def test_invariant_result_types(self):
        tester = InvariantTester()
        results = tester.run_all_tests()
        for name, result in results.items():
            assert isinstance(result.passed, bool)


class TestRealityScenarioRunner:
    """Tests for reality scenario runner."""

    def test_run_all_scenarios(self):
        runner = RealityScenarioRunner()
        results = runner.run_all_scenarios()
        assert isinstance(results, dict)

    def test_run_scenario(self):
        runner = RealityScenarioRunner()
        result = runner.run_scenario("val-a-file-creation")
        # May be None if scenario not found
        if result is not None:
            assert isinstance(result, RealityScenarioResult)


class TestRealityRunner:
    """Tests for the main reality runner."""

    def test_run_all(self):
        runner = RealityRunner()
        run = runner.run_all()
        assert isinstance(run, RealityRun)
        assert run.total_checks > 0

    def test_environment_captured(self):
        runner = RealityRunner()
        run = runner.run_all()
        assert run.environment is not None

    def test_totals_calculated(self):
        runner = RealityRunner()
        run = runner.run_all()
        assert run.total_checks >= run.passed + run.failed + run.skipped


class TestRealityEvaluator:
    """Tests for reality evaluator."""

    def test_evaluate(self):
        evaluator = RealityEvaluator()
        run = RealityRun(total_checks=10, passed=8, failed=2)
        evaluation = evaluator.evaluate(run)
        assert "summary" in evaluation
        assert "recommendations" in evaluation

    def test_compute_summary(self):
        evaluator = RealityEvaluator()
        run = RealityRun(total_checks=10, passed=8, failed=2)
        summary = evaluator._compute_summary(run)
        assert summary["pass_rate"] == 0.8


class TestRealityReporter:
    """Tests for reality reporter."""

    def test_generate_text_report(self):
        reporter = RealityReporter()
        run = RealityRun(total_checks=10, passed=8, failed=2)
        report = reporter.generate_text_report(run)
        assert "ARGUS 1.0.0" in report
        assert "RELEASE DECISION" in report

    def test_generate_json_report(self):
        reporter = RealityReporter()
        run = RealityRun(total_checks=10, passed=8, failed=2)
        report = reporter.generate_json_report(run)
        assert "report_type" in report
        assert "release_decision" in report


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_evaluate_reality_run(self):
        run = RealityRun(total_checks=10, passed=8, failed=2)
        evaluation = evaluate_reality_run(run)
        assert "summary" in evaluation

    def test_generate_reality_report(self):
        run = RealityRun(total_checks=10, passed=8, failed=2)
        report = generate_reality_report(run, "text")
        assert "ARGUS" in report

    def test_generate_reality_report_json(self):
        run = RealityRun(total_checks=10, passed=8, failed=2)
        report = generate_reality_report(run, "json")
        assert '"report_type"' in report
