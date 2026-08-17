import pytest
from pathlib import Path
from agentcore.verifier import Verifier, VerificationReport, CheckResult


class TestCheckResult:
    def test_check_result_to_dict(self):
        result = CheckResult(name="test", passed=True, output="ok")
        data = result.to_dict()
        
        assert data["name"] == "test"
        assert data["passed"] == True
        assert data["output"] == "ok"

    def test_check_result_with_error(self):
        result = CheckResult(name="test", passed=False, output="", error="Failed")
        data = result.to_dict()
        
        assert data["passed"] == False
        assert data["error"] == "Failed"


class TestVerificationReport:
    def test_report_overall_passed(self):
        report = VerificationReport(
            overall_passed=True,
            format_check=CheckResult(name="fmt", passed=True, output=""),
            build_check=CheckResult(name="build", passed=True, output=""),
        )
        
        assert report.overall_passed == True
        assert len(report.failures) == 0

    def test_report_with_failures(self):
        report = VerificationReport(
            overall_passed=False,
            failures=["Format check failed"],
        )
        
        assert report.overall_passed == False
        assert "Format check failed" in report.failures

    def test_to_dict(self):
        report = VerificationReport(overall_passed=True)
        data = report.to_dict()
        
        assert "overall_passed" in data
        assert "failures" in data


class TestVerifier:
    def test_detect_project_type_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        
        verifier = Verifier(tmp_path)
        assert verifier.project_type == "rust"

    def test_detect_project_type_python(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        
        verifier = Verifier(tmp_path)
        assert verifier.project_type == "python"

    def test_detect_project_type_js(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        
        verifier = Verifier(tmp_path)
        assert verifier.project_type == "javascript"

    def test_detect_unknown_project(self, tmp_path):
        verifier = Verifier(tmp_path)
        assert verifier.project_type == "unknown"

    def test_verify_all_skips_for_unknown(self, tmp_path):
        verifier = Verifier(tmp_path)
        
        report = verifier.verify_all(run_tests=False, run_format=False, run_build=False)
        
        assert report.overall_passed == True


class TestVerifierFailureClassification:
    def test_classify_pre_existing(self):
        verifier = Verifier()
        result = verifier.classify_failure("pre-existing issue found")
        assert result == "PRE_EXISTING"

    def test_classify_environmental(self):
        verifier = Verifier()
        result = verifier.classify_failure("permission denied")
        assert result == "ENVIRONMENTAL"

    def test_classify_current_change(self):
        verifier = Verifier()
        result = verifier.classify_failure("current change broke this")
        assert result == "CURRENT_CHANGE"

    def test_classify_unknown(self):
        verifier = Verifier()
        result = verifier.classify_failure("some random error")
        assert result == "UNKNOWN"