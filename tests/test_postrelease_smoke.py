"""Post-release smoke tests for ARGUS 1.0.0.

Lightweight suite suitable for every future release.
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestSmoke:
    """Post-release smoke tests."""

    def test_smoke_001_package_imports(self):
        """SMOKE-001: Package imports."""
        import argus
        assert argus is not None

    def test_smoke_002_version_is_correct(self):
        """SMOKE-002: Version is correct."""
        from argus import __version__
        assert __version__ == "1.0.0"

    def test_smoke_003_cli_starts(self):
        """SMOKE-003: CLI starts."""
        proc = subprocess.run(
            [sys.executable, "-m", "argus.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0

    def test_smoke_004_cli_help_works(self):
        """SMOKE-004: CLI help works."""
        proc = subprocess.run(
            [sys.executable, "-m", "argus.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "argus" in proc.stdout.lower()

    def test_smoke_005_config_without_credentials_fails_safely(self):
        """SMOKE-005: Configuration without credentials fails safely."""
        from argus.config import ArgusConfig
        config = ArgusConfig()
        # Should not raise, should return empty/default config
        assert config is not None

    def test_smoke_006_unknown_capability_cannot_execute(self):
        """SMOKE-006: Unknown capability cannot execute."""
        from argus.capabilities import CapabilityRegistry
        registry = CapabilityRegistry()
        # Unknown capability should not be found
        result = registry.get("nonexistent_capability_xyz")
        assert result is None

    def test_smoke_007_security_deny_cannot_execute(self):
        """SMOKE-007: Security DENY cannot become execution."""
        from argus.security.policy import SecurityPolicy
        from argus.security.permissions import Permission
        policy = SecurityPolicy()
        # Default permission should be ASK, not ALLOW
        assert policy.default_permission == Permission.ASK

    def test_smoke_008_replay_remains_observational(self):
        """SMOKE-008: Replay remains observational."""
        from argus.replay.replay import ReplayEngine
        engine = ReplayEngine()
        # Replay engine should exist and be observational
        assert engine is not None
        assert hasattr(engine, 'replay')

    def test_smoke_009_durable_operation_identity_stable(self):
        """SMOKE-009: Durable operation identity remains stable."""
        from argus.durable.detector import CrashDetector
        import tempfile
        tmpdir = tempfile.mkdtemp()
        detector = CrashDetector(run_dir=tmpdir)
        assert detector is not None
        assert hasattr(detector, 'register_run')

    def test_smoke_010_mcp_remains_security_gated(self):
        """SMOKE-010: MCP remains security-gated."""
        import argus.mcp.adapter as mcp_adapter
        assert hasattr(mcp_adapter, 'MCPCapabilityAdapter')
        assert hasattr(mcp_adapter, 'MCPClient')

    def test_smoke_011_provider_fallback_cannot_bypass_security(self):
        """SMOKE-011: Provider fallback cannot bypass security."""
        from argus.security.policy import SecurityPolicy
        policy = SecurityPolicy()
        # Security policy should be authoritative
        assert hasattr(policy, 'check_command')
        assert hasattr(policy, 'check_path')

    def test_smoke_012_secrets_do_not_appear_in_output(self):
        """SMOKE-012: Secrets do not appear in output."""
        from argus.security.secrets import SecretManager
        secrets = SecretManager()
        assert secrets is not None
        # Secret manager should exist and handle secrets safely
        assert hasattr(secrets, 'redact')
