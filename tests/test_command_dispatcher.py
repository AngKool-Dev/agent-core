"""Tests for Argus command dispatcher and REPL."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from argus.commands import CommandRegistry, build_registry
from argus.commands.help import handle as help_handle
from argus.commands.config import handle as config_handle
from argus.commands.agent import handle as agent_handle
from argus.commands.session import handle as session_handle
from argus.commands.tools import handle as tools_handle
from argus.commands.skills import handle as skills_handle
from argus.commands.memory import handle as memory_handle
from argus.commands.project import handle as project_handle


class TestCommandRegistry:
    """Tests for the command registry dispatch system."""

    def test_registry_builds_all_commands(self):
        registry = build_registry()
        expected = {"help", "exit", "quit", "clear", "session", "config",
                    "tools", "skills", "memory", "project", "agent",
                    "capabilities", "doctor", "trace", "review", "subagents",
                    "replay", "reality", "release"}
        assert set(registry._commands.keys()) == expected

    def test_handle_known_command(self):
        registry = CommandRegistry()
        mock_handler = MagicMock(return_value="result")
        registry.register("test", mock_handler)
        result = registry.handle("test", None, ["arg1"])
        assert result == "result"
        mock_handler.assert_called_once_with(None, ["arg1"])

    def test_handle_unknown_command(self):
        registry = CommandRegistry()
        result = registry.handle("nonexistent", None, [])
        assert "Unknown command" in result


class TestCommandHandlerSignatures:
    """Verify all command handlers have consistent (repl, args) signature."""

    @pytest.mark.parametrize("handler", [
        help_handle, config_handle, agent_handle,
        session_handle, tools_handle, skills_handle,
        memory_handle, project_handle,
    ])
    def test_handler_accepts_repl_and_args(self, handler):
        """All handlers must accept (repl, args) as positional args."""
        import inspect
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        assert len(params) == 2
        assert params[0].name == "repl"
        assert params[1].name == "args"

    def test_exit_handler(self):
        registry = build_registry()
        with pytest.raises(SystemExit):
            registry.handle("exit", None, [])

    def test_quit_handler(self):
        registry = build_registry()
        with pytest.raises(SystemExit):
            registry.handle("quit", None, [])

    def test_clear_handler(self):
        import argus.commands as cmd_module
        registry = build_registry()
        with patch.object(cmd_module, "os"):
            result = registry.handle("clear", None, [])
        assert result == ""


class TestHelpCommand:
    def test_help_returns_list(self):
        registry = build_registry()
        result = registry.handle("help", None, [])
        assert "Available commands:" in result

    def test_help_lists_all_commands(self):
        registry = build_registry()
        result = registry.handle("help", None, [])
        for cmd in ["exit", "quit", "clear", "session", "config", "tools",
                     "skills", "memory", "project", "agent"]:
            assert cmd in result

    def test_help_with_args_is_ignored(self):
        registry = build_registry()
        result = registry.handle("help", None, ["extra", "args"])
        assert "Available commands:" in result


class TestConfigCommand:
    def _make_repl(self, config=None):
        repl = MagicMock()
        from argus.config import ArgusConfig
        repl.config = config or ArgusConfig()
        return repl

    def test_config_show(self):
        repl = self._make_repl()
        registry = build_registry()
        result = registry.handle("config", repl, ["show"])
        assert "[agent]" in result or "[model]" in result or "[skills]" in result

    def test_config_show_handles_none_values(self):
        repl = self._make_repl()
        registry = build_registry()
        result = registry.handle("config", repl, ["show"])
        assert isinstance(result, str)

    def test_config_get_valid_key(self):
        repl = self._make_repl()
        registry = build_registry()
        result = registry.handle("config", repl, ["get", "model.name"])
        assert "model.name" in result

    def test_config_get_missing_key(self):
        repl = self._make_repl()
        registry = build_registry()
        result = registry.handle("config", repl, ["get", "nonexistent.key"])
        assert "None" in result or "nonexistent.key" in result

    def test_config_no_args(self):
        registry = build_registry()
        result = registry.handle("config", None, [])
        assert "Usage" in result


class TestToolsCommand:
    def test_tools_list(self):
        repl = MagicMock()
        from argus.config import ArgusConfig
        from argus.repl import ArgusREPL
        with patch.object(ArgusREPL, '__init__', return_value=None):
            repl = ArgusREPL.__new__(ArgusREPL)
            repl.tool_registry = MagicMock()
            repl.tool_registry.list_tools.return_value = [
                {"name": "read_file", "description": "Read a file"}
            ]
        registry = build_registry()
        result = registry.handle("tools", repl, ["list"])
        assert "read_file" in result

    def test_tools_no_args(self):
        registry = build_registry()
        result = registry.handle("tools", None, [])
        assert "Usage" in result


class TestSkillsCommand:
    def test_skills_list_no_skills(self):
        repl = MagicMock()
        repl.agent._skill_registry.list.return_value = []
        registry = build_registry()
        result = registry.handle("skills", repl, ["list"])
        assert "No skills" in result

    def test_skills_no_args(self):
        registry = build_registry()
        result = registry.handle("skills", None, [])
        assert "Usage" in result


class TestMemoryCommand:
    def test_memory_not_configured(self):
        repl = MagicMock()
        repl.agent.memory = MagicMock()
        repl.agent.memory.available = False
        registry = build_registry()
        result = registry.handle("memory", repl, ["summary"])
        assert "not configured" in result

    def test_memory_no_args(self):
        registry = build_registry()
        result = registry.handle("memory", None, [])
        assert "Usage" in result


class TestProjectCommand:
    def test_project_show(self):
        repl = MagicMock()
        from argus.context.project import ProjectProfile
        profile = ProjectProfile(root="/test")
        profile.name = "test-project"
        repl.agent._project_context = profile
        registry = build_registry()
        result = registry.handle("project", repl, [])
        assert "Project:" in result
        assert "Path:" in result


class TestAgentCommand:
    def test_agent_no_args(self):
        registry = build_registry()
        result = registry.handle("agent", None, [])
        assert "Usage" in result

    def test_agent_with_request(self):
        repl = MagicMock()
        repl.agent.execute.return_value = {
            "task_id": "test-1",
            "status": "COMPLETED",
            "success": True,
            "tool_results": [],
            "verification": {},
        }
        repl.agent.status.return_value = {
            "status": "COMPLETED",
            "tools_used": 0,
            "success": True,
            "skills": [],
        }
        registry = build_registry()
        result = registry.handle("agent", repl, ["hello"])
        assert "COMPLETED" in result or "PASSED" in result


class TestFormatter:
    def test_format_normal_result(self):
        from argus.formatter import format_agent_result
        result = {
            "tool_results": [
                {"tool": "read_file", "success": True},
                {"tool": "write_file", "success": False, "error": "Permission denied"},
            ],
            "verification": {},
            "success": True,
        }
        output = format_agent_result(result, verbose=False)
        assert "read_file" in output
        assert "write_file" in output

    def test_format_verbose_result(self):
        from argus.formatter import format_agent_result
        result = {
            "task_id": "task-1",
            "status": "COMPLETED",
            "iterations": 5,
            "tools_used": 3,
            "tool_results": [],
            "plan": [{"action": "investigate", "description": "Explore", "completed": True}],
            "verification": {},
            "success": True,
        }
        output = format_agent_result(result, verbose=True)
        assert "task-1" in output
        assert "COMPLETED" in output
        assert "Plan:" in output

    def test_format_empty_result(self):
        from argus.formatter import format_agent_result
        output = format_agent_result({"success": True}, verbose=False)
        assert "Done." == output or "successfully" in output

    def test_format_verification_checks(self):
        from argus.formatter import format_agent_result
        result = {
            "verification": {
                "format_check": {"passed": True},
                "build_check": {"passed": True},
                "test_results": {"passed": True, "total": 42},
            },
            "success": True,
            "tool_results": [],
        }
        output = format_agent_result(result, verbose=False)
        assert "42" in output

    def test_format_failed_verification(self):
        from argus.formatter import format_agent_result
        result = {
            "verification": {
                "format_check": {"passed": False},
                "test_results": {"passed": False},
            },
            "success": False,
            "error": "Build failed",
            "tool_results": [],
        }
        output = format_agent_result(result, verbose=False)
        assert "FAIL" in output


class TestArgusDefaultReasoner:
    """Test the built-in default reasoner for file creation requests."""

    def test_extract_file_creation_request(self):
        from argus.agent import ArgusAgent
        agent = ArgusAgent(project_path=Path.cwd(), model=None)
        lines = agent._extract_file_creation_request(
            "create a file called hello.py containing a Python program that prints Hello Argus.",
            "Create a file called hello.py containing a Python program that prints Hello Argus."
        )
        assert len(lines) == 1
        assert lines[0]["tool"] == "write_file"
        args = lines[0]["arguments"]
        assert "hello.py" in args["path"]
        assert "Hello Argus" in args["content"]
        assert "print" in args["content"]
