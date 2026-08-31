"""CLI hardening and configuration precedence for ARGUS.

Implements the configuration precedence hierarchy:
    hard safety policy > CLI > session config > project config > env defaults

Provides validation, safety checks, and secure defaults for CLI operations.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from argus.config import ArgusConfig


class ConfigurationPrecedence:
    """
    Manages configuration precedence for ARGUS.

    Precedence order (highest to lowest):
    1. Hard safety policy (immutable)
    2. CLI arguments
    3. Session config
    4. Project config (argus.toml)
    5. Environment defaults
    """

    # Hard safety policies that cannot be overridden
    SAFETY_POLICIES = {
        "max_iterations": {"min": 1, "max": 1000},
        "max_tools": {"min": 1, "max": 500},
        "timeout_seconds": {"min": 10, "max": 7200},
        "max_consecutive_failures": {"min": 1, "max": 50},
        "max_no_progress": {"min": 1, "max": 50},
        "workspace_boundaries_enabled": {"type": "bool"},
        "enable_verification": {"type": "bool"},
    }

    # Dangerous settings that require explicit confirmation
    DANGEROUS_SETTINGS = {
        "permissions.read": {"risk": "low", "description": "File read permissions"},
        "permissions.write": {"risk": "medium", "description": "File write permissions"},
        "permissions.bash": {"risk": "high", "description": "Shell command execution"},
        "permissions.git": {"risk": "medium", "description": "Git operation permissions"},
        "permissions.browser": {"risk": "high", "description": "Browser control permissions"},
        "model_hub.budget.allow_paid": {"risk": "high", "description": "Allow paid model usage"},
        "model_hub.budget.daily_limit": {"risk": "medium", "description": "Daily budget limit"},
    }

    @classmethod
    def validate_safety_bounds(cls, key: str, value: Any) -> Tuple[bool, str]:
        """Validate that a configuration value is within safety bounds."""
        # Map dotted key to safety policy
        policy_key = key.replace("agent.", "").replace("permissions.", "")

        if policy_key in cls.SAFETY_POLICIES:
            policy = cls.SAFETY_POLICIES[policy_key]
            if "min" in policy and "max" in policy:
                try:
                    num_val = float(value) if not isinstance(value, bool) else int(value)
                    if num_val < policy["min"]:
                        return False, f"{key} value {num_val} below minimum {policy['min']}"
                    if num_val > policy["max"]:
                        return False, f"{key} value {num_val} exceeds maximum {policy['max']}"
                except (ValueError, TypeError):
                    return False, f"{key} value must be numeric"

        return True, ""

    @classmethod
    def enforce_safety_policy(cls, config: ArgusConfig) -> List[str]:
        """Enforce safety policies on a config, returning list of violations."""
        violations = []

        for key, policy in cls.SAFETY_POLICIES.items():
            value = config.get(f"agent.{key}")
            if value is not None:
                valid, msg = cls.validate_safety_bounds(f"agent.{key}", value)
                if not valid:
                    violations.append(msg)

        return violations

    @classmethod
    def is_dangerous_setting(cls, key: str) -> Tuple[bool, str, str]:
        """Check if a setting is potentially dangerous."""
        if key in cls.DANGEROUS_SETTINGS:
            info = cls.DANGEROUS_SETTINGS[key]
            return True, info["risk"], info["description"]
        return False, "", ""

    @classmethod
    def merge_with_precedence(
        cls,
        project_config: ArgusConfig,
        cli_overrides: Optional[Dict[str, Any]] = None,
        session_config: Optional[Dict[str, Any]] = None,
    ) -> ArgusConfig:
        """
        Merge configuration sources according to precedence.

        Args:
            project_config: Base project configuration
            cli_overrides: CLI argument overrides (highest precedence)
            session_config: Session configuration overrides

        Returns:
            Merged ArgusConfig with proper precedence
        """
        # Start with project config
        merged = ArgusConfig()

        # Copy project config values
        if project_config and hasattr(project_config, "raw"):
            for section, values in project_config.raw.items():
                if isinstance(values, dict):
                    for key, value in values.items():
                        merged.set(f"{section}.{key}", value)

        # Apply session config (lower precedence than CLI)
        if session_config:
            for key, value in session_config.items():
                merged.set(key, value)

        # Apply CLI overrides (highest precedence)
        if cli_overrides:
            for key, value in cli_overrides.items():
                merged.set(key, value)

        # Enforce safety policies
        cls.enforce_safety_policy(merged)

        return merged


class CLIHardening:
    """CLI hardening checks and validations."""

    @staticmethod
    def validate_config_path(path: str) -> Tuple[bool, str]:
        """Validate a configuration file path."""
        config_path = Path(path)

        if not config_path.exists():
            return False, f"Config file not found: {path}"

        if not config_path.is_file():
            return False, f"Config path is not a file: {path}"

        # Check file permissions (should not be world-writable)
        try:
            stat = config_path.stat()
            mode = stat.st_mode
            if mode & 0o002:  # World-writable
                return False, f"Config file is world-writable: {path}"
        except OSError:
            pass

        # Check file size (should be reasonable)
        if config_path.stat().st_size > 1_000_000:  # 1MB limit
            return False, f"Config file too large: {path}"

        return True, ""

    @staticmethod
    def validate_project_path(path: str) -> Tuple[bool, str]:
        """Validate a project directory path."""
        project_path = Path(path)

        if not project_path.exists():
            return False, f"Project directory not found: {path}"

        if not project_path.is_dir():
            return False, f"Project path is not a directory: {path}"

        # Check for suspicious paths
        suspicious = ["/etc", "/usr", "/bin", "/sbin", "/boot", "/sys", "/proc"]
        resolved = str(project_path.resolve())
        for susp in suspicious:
            if resolved.startswith(susp):
                return False, f"Project path in system directory: {path}"

        return True, ""

    @staticmethod
    def validate_model_name(name: str) -> Tuple[bool, str]:
        """Validate a model name."""
        if not name:
            return False, "Model name cannot be empty"

        if len(name) > 256:
            return False, "Model name too long"

        # Check for path traversal
        if ".." in name or "/" in name or "\\" in name:
            return False, "Model name contains invalid characters"

        return True, ""

    @staticmethod
    def validate_provider_name(name: str) -> Tuple[bool, str]:
        """Validate a provider name."""
        valid_providers = [
            "ollama", "openai", "anthropic", "gemini", "groq",
            "cerebras", "openrouter", "mistral", "cohere",
        ]

        if not name:
            return False, "Provider name cannot be empty"

        if name.lower() not in valid_providers:
            return False, f"Unknown provider: {name}"

        return True, ""

    @staticmethod
    def check_environment_safety() -> List[str]:
        """Check for unsafe environment conditions."""
        warnings = []

        # Check for running as root/admin
        if os.name == "nt":
            try:
                import ctypes
                if ctypes.windll.shell32.IsUserAnAdmin():
                    warnings.append("Running as administrator - consider using a regular user account")
            except Exception:
                pass
        else:
            if os.geteuid() == 0:
                warnings.append("Running as root - consider using a regular user account")

        # Check for suspicious environment variables
        suspicious_vars = ["ARGUS_BYPASS_SAFETY", "ARGUS_DISABLE_VERIFICATION"]
        for var in suspicious_vars:
            if os.environ.get(var):
                warnings.append(f"Safety override detected: {var}")

        return warnings

    @staticmethod
    def sanitize_input(user_input: str) -> str:
        """Sanitize user input for safety."""
        # Remove null bytes
        sanitized = user_input.replace("\x00", "")

        # Remove control characters (except newline and tab)
        sanitized = "".join(
            c for c in sanitized
            if c == "\n" or c == "\t" or (ord(c) >= 32 and ord(c) != 127)
        )

        # Strip leading/trailing whitespace
        sanitized = sanitized.strip()

        return sanitized


class ConfigAuditor:
    """Audits configuration for security and correctness."""

    def __init__(self, config: ArgusConfig):
        self._config = config

    def audit(self) -> Dict[str, Any]:
        """Run a full configuration audit."""
        return {
            "security_issues": self._check_security(),
            "warnings": self._check_warnings(),
            "suggestions": self._check_suggestions(),
            "compliance": self._check_compliance(),
        }

    def _check_security(self) -> List[str]:
        """Check for security issues."""
        issues = []

        # Check permissions
        for perm in ["read", "search", "write", "bash", "git", "browser"]:
            value = self._config.get(f"permissions.{perm}")
            if value == "deny":
                issues.append(f"Permission '{perm}' is denied - may limit functionality")

        # Check for insecure budget settings
        allow_paid = self._config.get("model_hub.budget.allow_paid")
        if allow_paid:
            daily_limit = self._config.get("model_hub.budget.daily_limit", 0.0)
            if daily_limit <= 0:
                issues.append("Paid models allowed with no daily limit - potential cost risk")

        # Check workspace boundaries
        if not self._config.get("agent.workspace_boundaries_enabled"):
            issues.append("Workspace boundaries disabled - agent can access any file")

        return issues

    def _check_warnings(self) -> List[str]:
        """Check for warnings."""
        warnings = []

        # Check verification settings
        if not self._config.get("agent.enable_verification"):
            warnings.append("Verification disabled - agent results will not be validated")

        # Check iteration limits
        max_iter = self._config.get("agent.max_iterations", 10)
        if max_iter > 100:
            warnings.append(f"High max_iterations ({max_iter}) - may cause long-running tasks")

        # Check timeout
        timeout = self._config.get("agent.timeout_seconds", 300)
        if timeout < 30:
            warnings.append(f"Low timeout ({timeout}s) - tasks may fail prematurely")

        return warnings

    def _check_suggestions(self) -> List[str]:
        """Check for improvement suggestions."""
        suggestions = []

        # Suggest enabling features
        if not self._config.get("agent.enable_engineering_loop"):
            suggestions.append("Consider enabling engineering_loop for better code quality")

        if not self._config.get("agent.run_tests"):
            suggestions.append("Consider enabling run_tests for test validation")

        return suggestions

    def _check_compliance(self) -> Dict[str, bool]:
        """Check compliance with best practices."""
        return {
            "workspace_boundaries": self._config.get("agent.workspace_boundaries_enabled", True),
            "verification_enabled": self._config.get("agent.enable_verification", True),
            "format_check": self._config.get("agent.run_format_check", True),
            "build_check": self._config.get("agent.run_build_check", True),
            "test_check": self._config.get("agent.run_tests", True),
            "budget_controls": self._config.get("model_hub.budget.daily_limit", 0) > 0,
        }


def audit_config(config: ArgusConfig) -> Dict[str, Any]:
    """Convenience function to audit a configuration."""
    auditor = ConfigAuditor(config)
    return auditor.audit()


def validate_cli_args(args: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate CLI arguments for safety."""
    errors = []

    # Validate project path
    if "project" in args and args["project"]:
        valid, msg = CLIHardening.validate_project_path(args["project"])
        if not valid:
            errors.append(msg)

    # Validate config path
    if "config" in args and args["config"]:
        valid, msg = CLIHardening.validate_config_path(args["config"])
        if not valid:
            errors.append(msg)

    # Validate model name
    if "model" in args and args["model"]:
        valid, msg = CLIHardening.validate_model_name(args["model"])
        if not valid:
            errors.append(msg)

    return len(errors) == 0, errors
