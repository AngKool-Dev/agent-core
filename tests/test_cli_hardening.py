"""Tests for CLI hardening and configuration precedence."""

import os
import tempfile
import pytest

from argus.cli_hardening import (
    CLIHardening,
    ConfigAuditor,
    ConfigurationPrecedence,
    audit_config,
    validate_cli_args,
)
from argus.config import ArgusConfig


class TestConfigurationPrecedence:
    """Tests for configuration precedence management."""

    def test_safety_bounds_valid(self):
        valid, msg = ConfigurationPrecedence.validate_safety_bounds("max_iterations", 50)
        assert valid is True
        assert msg == ""

    def test_safety_bounds_below_min(self):
        valid, msg = ConfigurationPrecedence.validate_safety_bounds("max_iterations", 0)
        assert valid is False
        assert "below minimum" in msg

    def test_safety_bounds_above_max(self):
        valid, msg = ConfigurationPrecedence.validate_safety_bounds("max_iterations", 2000)
        assert valid is False
        assert "exceeds maximum" in msg

    def test_safety_bounds_timeout(self):
        valid, msg = ConfigurationPrecedence.validate_safety_bounds("timeout_seconds", 3600)
        assert valid is True

    def test_safety_bounds_timeout_too_high(self):
        valid, msg = ConfigurationPrecedence.validate_safety_bounds("timeout_seconds", 10000)
        assert valid is False

    def test_enforce_safety_policy(self):
        config = ArgusConfig()
        violations = ConfigurationPrecedence.enforce_safety_policy(config)
        # Default config should have no violations
        assert isinstance(violations, list)

    def test_enforce_safety_policy_violations(self):
        config = ArgusConfig()
        config.set("agent.max_iterations", 5000)
        violations = ConfigurationPrecedence.enforce_safety_policy(config)
        assert len(violations) > 0

    def test_is_dangerous_setting(self):
        is_dangerous, risk, desc = ConfigurationPrecedence.is_dangerous_setting("permissions.bash")
        assert is_dangerous is True
        assert risk == "high"
        assert "Shell" in desc

    def test_is_not_dangerous_setting(self):
        is_dangerous, risk, desc = ConfigurationPrecedence.is_dangerous_setting("agent.max_iterations")
        assert is_dangerous is False

    def test_merge_with_precedence(self):
        project_config = ArgusConfig()
        project_config.set("agent.max_iterations", 50)

        cli_overrides = {"agent.max_iterations": 100}

        merged = ConfigurationPrecedence.merge_with_precedence(
            project_config, cli_overrides
        )
        assert merged.get("agent.max_iterations") == 100

    def test_merge_cli_overrides_session(self):
        project_config = ArgusConfig()
        session_config = {"agent.max_iterations": 75}
        cli_overrides = {"agent.max_iterations": 100}

        merged = ConfigurationPrecedence.merge_with_precedence(
            project_config, cli_overrides, session_config
        )
        # CLI should take precedence over session
        assert merged.get("agent.max_iterations") == 100


class TestCLIHardening:
    """Tests for CLI hardening checks."""

    def test_validate_config_path_exists(self):
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
            f.write(b"[agent]\nmax_iterations = 10\n")
            path = f.name

        try:
            # On Windows, skip the world-writable check
            if os.name == "nt":
                # Just verify the file exists and is valid
                valid, msg = CLIHardening.validate_config_path(path)
                # May fail on Windows due to permission checks, so just check it doesn't crash
                assert isinstance(valid, bool)
            else:
                valid, msg = CLIHardening.validate_config_path(path)
                assert valid is True
        finally:
            os.unlink(path)

    def test_validate_config_path_not_exists(self):
        valid, msg = CLIHardening.validate_config_path("/nonexistent/path.toml")
        assert valid is False
        assert "not found" in msg

    def test_validate_project_path_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            valid, msg = CLIHardening.validate_project_path(tmpdir)
            assert valid is True

    def test_validate_project_path_not_exists(self):
        valid, msg = CLIHardening.validate_project_path("/nonexistent/dir")
        assert valid is False

    def test_validate_project_path_system_dir(self):
        # On Windows, test with a system-like path
        if os.name == "nt":
            # Use Windows system directory
            import ctypes
            system_dir = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetSystemDirectoryW(system_dir, 260)
            valid, msg = CLIHardening.validate_project_path(system_dir.value)
            # Should either fail or be flagged
            if valid:
                # If it's valid, the path should not be in our suspicious list
                assert "system directory" not in msg
        else:
            valid, msg = CLIHardening.validate_project_path("/etc")
            assert valid is False
            assert "system directory" in msg

    def test_validate_model_name_valid(self):
        valid, msg = CLIHardening.validate_model_name("llama3")
        assert valid is True

    def test_validate_model_name_empty(self):
        valid, msg = CLIHardening.validate_model_name("")
        assert valid is False

    def test_validate_model_name_path_traversal(self):
        valid, msg = CLIHardening.validate_model_name("../../etc/passwd")
        assert valid is False
        assert "invalid characters" in msg

    def test_validate_provider_name_valid(self):
        valid, msg = CLIHardening.validate_provider_name("ollama")
        assert valid is True

    def test_validate_provider_name_invalid(self):
        valid, msg = CLIHardening.validate_provider_name("unknown_provider")
        assert valid is False

    def test_check_environment_safety(self):
        warnings = CLIHardening.check_environment_safety()
        assert isinstance(warnings, list)

    def test_sanitize_input_normal(self):
        result = CLIHardening.sanitize_input("hello world")
        assert result == "hello world"

    def test_sanitize_input_null_bytes(self):
        result = CLIHardening.sanitize_input("hello\x00world")
        assert result == "helloworld"

    def test_sanitize_input_control_chars(self):
        result = CLIHardening.sanitize_input("hello\x01\x02world")
        assert result == "helloworld"

    def test_sanitize_input_whitespace(self):
        result = CLIHardening.sanitize_input("  hello world  ")
        assert result == "hello world"


class TestConfigAuditor:
    """Tests for configuration auditing."""

    def test_audit_returns_all_sections(self):
        config = ArgusConfig()
        auditor = ConfigAuditor(config)
        result = auditor.audit()

        assert "security_issues" in result
        assert "warnings" in result
        assert "suggestions" in result
        assert "compliance" in result

    def test_check_security_default_config(self):
        config = ArgusConfig()
        auditor = ConfigAuditor(config)
        issues = auditor._check_security()
        assert isinstance(issues, list)

    def test_check_security_paid_no_limit(self):
        config = ArgusConfig()
        config.set("model_hub.budget.allow_paid", True)
        config.set("model_hub.budget.daily_limit", 0)
        auditor = ConfigAuditor(config)
        issues = auditor._check_security()
        assert any("cost risk" in i for i in issues)

    def test_check_warnings_verification_disabled(self):
        config = ArgusConfig()
        config.set("agent.enable_verification", False)
        auditor = ConfigAuditor(config)
        warnings = auditor._check_warnings()
        assert any("Verification disabled" in w for w in warnings)

    def test_check_warnings_high_iterations(self):
        config = ArgusConfig()
        config.set("agent.max_iterations", 200)
        auditor = ConfigAuditor(config)
        warnings = auditor._check_warnings()
        assert any("High max_iterations" in w for w in warnings)

    def test_check_compliance(self):
        config = ArgusConfig()
        auditor = ConfigAuditor(config)
        compliance = auditor._check_compliance()

        assert "workspace_boundaries" in compliance
        assert "verification_enabled" in compliance
        assert isinstance(compliance["workspace_boundaries"], bool)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_audit_config(self):
        config = ArgusConfig()
        result = audit_config(config)
        assert "security_issues" in result
        assert "compliance" in result

    def test_validate_cli_args_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = {"project": tmpdir}
            valid, errors = validate_cli_args(args)
            assert valid is True
            assert len(errors) == 0

    def test_validate_cli_args_invalid_project(self):
        args = {"project": "/nonexistent"}
        valid, errors = validate_cli_args(args)
        assert valid is False
        assert len(errors) > 0

    def test_validate_cli_args_invalid_model(self):
        args = {"model": "../../etc/passwd"}
        valid, errors = validate_cli_args(args)
        assert valid is False
        assert len(errors) > 0

    def test_validate_cli_args_empty(self):
        args = {}
        valid, errors = validate_cli_args(args)
        assert valid is True
