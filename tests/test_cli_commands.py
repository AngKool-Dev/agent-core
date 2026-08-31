"""Tests for new CLI commands (capabilities, doctor, trace)."""

import pytest
from typing import List
from unittest.mock import MagicMock, patch


def _mock_health_check(self):
    """Mock health check that doesn't run real tools."""
    return {"status": "healthy", "message": "mocked"}


class FakeRepl:
    """Fake REPL for testing commands."""

    def __init__(self):
        from argus.tools import ToolRegistry
        from argus.permissions import PermissionConfig

        self.tool_registry = MagicMock(spec=ToolRegistry)
        self.tool_registry.list_tools.return_value = [
            {"name": "bash", "description": "Execute a shell command"},
            {"name": "read_file", "description": "Read a file"},
        ]
        self._cap_router = None
        self.model_router = None


class TestCapabilitiesCommand:
    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_list(self):
        """Test /capabilities list command."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["list"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_no_args(self):
        """Test /capabilities with no args."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, [])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_search(self):
        """Test /capabilities search command."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["search", "execute"])
        assert isinstance(result, str)

    def test_capabilities_search_no_query(self):
        """Test /capabilities search without query."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["search"])
        assert "Usage" in result

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_show(self):
        """Test /capabilities show command."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["show", "shell.execute"])
        assert isinstance(result, str)

    def test_capabilities_show_no_id(self):
        """Test /capabilities show without id."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["show"])
        assert "Usage" in result

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_types(self):
        """Test /capabilities types command."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["types"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_stats(self):
        """Test /capabilities stats command."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["stats"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_discover(self):
        """Test /capabilities discover command."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["discover"])
        assert isinstance(result, str)

    def test_capabilities_unknown(self):
        """Test /capabilities with unknown subcommand."""
        from argus.commands.capabilities import handle

        repl = FakeRepl()
        result = handle(repl, ["unknown"])
        assert "Unknown" in result


class TestDoctorCommand:
    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_doctor_full(self):
        """Test /doctor full command."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, ["full"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_doctor_no_args(self):
        """Test /doctor with no args."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, [])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_doctor_capabilities(self):
        """Test /doctor capabilities command."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, ["capabilities"])
        assert isinstance(result, str)

    def test_doctor_models(self):
        """Test /doctor models command."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, ["models"])
        assert isinstance(result, str)

    def test_doctor_tools(self):
        """Test /doctor tools command."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, ["tools"])
        assert isinstance(result, str)

    def test_doctor_system(self):
        """Test /doctor system command."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, ["system"])
        assert "Python" in result
        assert "Platform" in result

    def test_doctor_unknown(self):
        """Test /doctor with unknown subcommand."""
        from argus.commands.doctor import handle

        repl = FakeRepl()
        result = handle(repl, ["unknown"])
        assert "Unknown" in result


class TestTraceCommand:
    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_recent(self):
        """Test /trace recent command."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["recent"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_recent_with_limit(self):
        """Test /trace recent with limit."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["recent", "5"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_no_args(self):
        """Test /trace with no args."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, [])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_capability(self):
        """Test /trace capability command."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["capability", "shell.execute"])
        assert isinstance(result, str)

    def test_trace_capability_no_id(self):
        """Test /trace capability without id."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["capability"])
        assert "Usage" in result

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_clear(self):
        """Test /trace clear command."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["clear"])
        assert "cleared" in result.lower() or "clear" in result.lower()

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_stats(self):
        """Test /trace stats command."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["stats"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_export(self):
        """Test /trace export command."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["export", "/tmp/test_trace.json"])
        assert isinstance(result, str)

    def test_trace_unknown(self):
        """Test /trace with unknown subcommand."""
        from argus.commands.trace import handle

        repl = FakeRepl()
        result = handle(repl, ["unknown"])
        assert "Unknown" in result


class TestCommandRegistry:
    def test_new_commands_registered(self):
        """Test that new commands are registered."""
        from argus.commands import build_registry

        registry = build_registry()
        assert registry._commands.get("capabilities") is not None
        assert registry._commands.get("doctor") is not None
        assert registry._commands.get("trace") is not None

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_capabilities_command_runs(self):
        """Test that /capabilities command can be executed via registry."""
        from argus.commands import build_registry

        registry = build_registry()
        repl = FakeRepl()
        result = registry.handle("capabilities", repl, ["list"])
        assert isinstance(result, str)

    def test_doctor_command_runs(self):
        """Test that /doctor command can be executed via registry."""
        from argus.commands import build_registry

        registry = build_registry()
        repl = FakeRepl()
        result = registry.handle("doctor", repl, ["system"])
        assert isinstance(result, str)

    @patch('argus.capabilities.adapter.ToolCapabilityAdapter.health_check', _mock_health_check)
    def test_trace_command_runs(self):
        """Test that /trace command can be executed via registry."""
        from argus.commands import build_registry

        registry = build_registry()
        repl = FakeRepl()
        result = registry.handle("trace", repl, ["recent"])
        assert isinstance(result, str)