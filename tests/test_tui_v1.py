"""Regression tests for Argus TUI v1 REPL features."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from argus.commands import build_registry, _COMMAND_GROUPS
from argus.config import ArgusConfig
from argus.formatter import format_agent_result


def make_repl():
    """Create a mocked ArgusREPL instance without running __init__."""
    from argus.repl import ArgusREPL
    with patch.object(ArgusREPL, '__init__', return_value=None):
        repl = ArgusREPL.__new__(ArgusREPL)
        repl.config = ArgusConfig()
        repl.verbose = False
        repl.commands = build_registry()
        repl.session = MagicMock()
        repl.tool_registry = MagicMock()
        repl.agent = MagicMock()
        repl.agent.execute.return_value = {
            "success": True, "status": "COMPLETED",
            "tool_results": [], "final_response": "Done"
        }
        repl._use_prompt_toolkit = False
        repl._status_active = False
        repl._status_lines = []
        repl._spinner_thread = None
        repl._project_path = Path(".")
        repl._credentials = MagicMock()
        repl._credentials.list_providers.return_value = {}
        repl.session_manager = MagicMock()
        return repl


class TestSlashCommandParsing:
    """Tests for slash command parsing and dispatch."""

    def test_slash_command_dispatch(self):
        repl = make_repl()
        result = repl._handle_command("/help")
        assert "Available commands" in result

    def test_slash_command_with_args(self):
        repl = make_repl()
        result = repl._handle_command("/config get model.name")
        assert "model.name" in result

    def test_unknown_slash_command(self):
        repl = make_repl()
        result = repl._handle_command("/nonexistent")
        assert "Unknown command" in result

    def test_empty_slash_command(self):
        repl = make_repl()
        result = repl._handle_command("/")
        assert result == ""


class TestBareExit:
    """Tests that bare 'exit'/'quit' (without slash) exits the REPL."""

    def test_bare_exit_exits_cleanly(self):
        repl = make_repl()

        call_count = [0]
        def fake_read_input():
            call_count[0] += 1
            if call_count[0] == 1:
                return "exit"
            return "/exit"

        with patch.object(repl, '_print_header'), \
             patch.object(repl, '_print_startup_info'), \
             patch.object(repl, '_stop_spinner'):
            repl._read_input = fake_read_input
            result = repl.run()

        assert result == 0


class TestCommandAutocomplete:
    """Tests for slash command autocomplete data."""

    def _make_completer(self):
        from argus.repl import ArgusCompleter
        return ArgusCompleter(["help", "exit", "agent", "model", "memory",
                               "session", "skills", "project", "config", "tools", "clear",
                               "providers", "models", "quit"])

    def test_completer_provides_suggestions(self):
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer()
        doc = Document(text="/", cursor_position=1)
        completions = list(completer.get_completions(doc, CompleteEvent()))
        assert len(completions) >= 10

    def test_completer_filters_by_prefix_m(self):
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer()
        doc = Document(text="/m", cursor_position=2)
        completions = list(completer.get_completions(doc, CompleteEvent()))
        names = [c.text for c in completions]
        assert "/model" in names or "/memory" in names
        assert "/exit" not in names
        assert "/agent" not in names

    def test_completer_filters_by_prefix_s(self):
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer()
        doc = Document(text="/s", cursor_position=2)
        completions = list(completer.get_completions(doc, CompleteEvent()))
        names = [c.text for c in completions]
        assert "/session" in names
        assert "/skills" in names
        assert "/model" not in names
        assert "/memory" not in names

    def test_completer_empty_after_space(self):
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer()
        doc = Document(text="/help ", cursor_position=6)
        completions = list(completer.get_completions(doc, CompleteEvent()))
        assert len(completions) == 0

    def test_command_names_list(self):
        from argus.repl import _get_command_names
        names = _get_command_names()
        assert "help" in names
        assert "exit" in names
        assert "agent" in names
        assert "model" in names
        assert "providers" in names

    def test_all_commands_in_names(self):
        from argus.repl import _get_command_names
        names = set(_get_command_names())
        for required in ["agent", "project", "clear", "model", "providers", "models",
                         "memory", "skills", "session", "config", "tools",
                         "help", "exit"]:
            assert required in names, f"Missing: {required}"


class TestNaturalLanguageInput:
    """Tests that natural language input goes to agent."""

    def test_chat_input_dispatches_to_agent(self):
        repl = make_repl()
        repl.session = MagicMock()

        with patch.object(repl, '_start_spinner'), \
             patch.object(repl, '_stop_spinner'), \
             patch.object(repl, '_print'):
            repl._handle_message("explain this project")

        repl.agent.execute.assert_called_once_with("explain this project")


class TestHelpCommand:
    """Tests for the /help command output."""

    def test_help_short_lists_commands(self):
        registry = build_registry()
        result = registry.handle("help", None, [])
        assert "Available commands:" in result
        for cmd in ["exit", "clear", "session", "config", "tools",
                     "skills", "memory", "project", "agent", "help"]:
            assert cmd in result

    def test_help_full_categorized(self):
        registry = build_registry()
        result = registry.handle("help", None, ["full"])
        assert "Tip:" in result

    def test_help_with_extra_args(self):
        registry = build_registry()
        result = registry.handle("help", None, ["extra", "args"])
        assert "Available commands:" in result


class TestUnknownCommand:
    """Tests for unknown command handling."""

    def test_unknown_command_message(self):
        registry = build_registry()
        result = registry.handle("nonexistent", None, [])
        assert "Unknown command" in result


class TestEmptyInput:
    """Tests for empty input handling in command parsing."""

    def test_empty_slash_command_returns_empty(self):
        repl = make_repl()
        result = repl._handle_command("/")
        assert result == ""

    def test_empty_input_string(self):
        parts = "".split()
        assert parts == []


class TestCtrlCHandling:
    """Tests for Ctrl+C / KeyboardInterrupt handling."""

    def test_keyboard_interrupt_during_input(self):
        repl = make_repl()

        call_count = [0]
        def fake_read_input():
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyboardInterrupt
            return "/exit"

        with patch.object(repl, '_print_header'), \
             patch.object(repl, '_print_startup_info'), \
             patch.object(repl, '_stop_spinner'), \
             patch.object(repl, '_print'), \
             patch.object(repl, '_start_spinner'):
            repl._read_input = fake_read_input
            result = repl.run()

        assert result == 0

    def test_keyboard_interrupt_during_agent(self):
        repl = make_repl()
        repl.agent.execute.side_effect = KeyboardInterrupt()

        call_count = [0]
        def fake_read_input():
            call_count[0] += 1
            if call_count[0] == 1:
                return "list files"
            return "/exit"

        with patch.object(repl, '_print_header'), \
             patch.object(repl, '_print_startup_info'), \
             patch.object(repl, '_stop_spinner'), \
             patch.object(repl, '_print'), \
             patch.object(repl, '_start_spinner'):
            repl._read_input = fake_read_input
            result = repl.run()

        repl.agent.cancel.assert_called()

    def test_keyboard_interrupt_at_empty_prompt_does_not_traceback(self):
        repl = make_repl()

        call_count = [0]
        def fake_read_input():
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyboardInterrupt
            return "/exit"

        with patch.object(repl, '_print_header'), \
             patch.object(repl, '_print_startup_info'), \
             patch.object(repl, '_stop_spinner'), \
             patch.object(repl, '_print'):
            repl._read_input = fake_read_input
            result = repl.run()

        assert result == 0


class TestStartupModelStatus:
    """Tests for startup model status detection."""

    def test_status_local(self):
        repl = make_repl()
        repl._credentials.list_providers.return_value = {}
        status = repl._determine_model_status()
        assert status["mode"] in ("Local", "Local fallback")
        assert "provider" in status

    def test_status_byok(self):
        from argus.repl import ArgusREPL
        with patch.object(ArgusREPL, '__init__', return_value=None):
            repl = ArgusREPL.__new__(ArgusREPL)
            repl.config = ArgusConfig()
            repl._credentials = MagicMock()
            repl._credentials.list_providers.return_value = {}
            repl._credentials.get = MagicMock(return_value="fake-key")
            repl.config.set("providers.openai.api_key", "config-key")
            status = repl._determine_model_status()
            assert status["mode"] == "BYOK"

    def test_status_gateway_unavailable(self):
        repl = make_repl()
        repl.config.set("gateway.base_url", "http://nonexistent-gateway.invalid")
        with patch("argus.repl._check_gateway_available", return_value=False):
            status = repl._determine_model_status()
            assert "unreachable" in status["status"].lower()


class TestUnavailableModelStatus:
    """Tests for unavailable model status display."""

    def test_no_model_shows_status(self):
        repl = make_repl()
        repl._credentials.list_providers.return_value = {}
        status = repl._determine_model_status()
        assert "status" in status
        assert status["status"] is not None

    def test_gateway_unreachable_shows_status(self):
        repl = make_repl()
        repl.config.set("gateway.base_url", "http://nonexistent.invalid")
        with patch("argus.repl._check_gateway_available", return_value=False):
            status = repl._determine_model_status()
            assert "not" in status["status"].lower() or "unreachable" in status["status"].lower()


class TestFormatterOutput:
    """Tests for formatter output."""

    def test_format_success(self):
        result = {
            "success": True,
            "tool_results": [{"tool": "write_file", "success": True}],
            "verification": {},
        }
        output = format_agent_result(result, verbose=False)
        assert "Completed" in output

    def test_format_with_tool_results(self):
        result = {
            "success": True,
            "tool_results": [
                {"tool": "read_file", "success": True},
                {"tool": "write_file", "success": True},
            ],
            "verification": {},
        }
        output = format_agent_result(result, verbose=False)
        assert "read_file" in output
        assert "write_file" in output

    def test_format_with_failed_tool(self):
        result = {
            "success": True,
            "tool_results": [
                {"tool": "read_file", "success": True},
                {"tool": "bash", "success": False, "error": "command not found"},
            ],
            "verification": {},
        }
        output = format_agent_result(result, verbose=False)
        assert "FAIL" in output

    def test_format_with_verification(self):
        result = {
            "success": True,
            "tool_results": [],
            "verification": {
                "test_results": {"passed": True, "total": 42},
            },
        }
        output = format_agent_result(result, verbose=False)
        assert "42" in output

    def test_format_empty_result(self):
        output = format_agent_result({"success": True}, verbose=False)
        assert "Done." == output or "successfully" in output

    def test_format_failure(self):
        result = {
            "success": False,
            "error": "Something went wrong",
            "tool_results": [],
            "verification": {},
        }
        output = format_agent_result(result, verbose=False)
        assert "issues" in output.lower()

    def test_format_verbose_includes_plan(self):
        result = {
            "task_id": "task-1",
            "status": "COMPLETED",
            "iterations": 3,
            "tools_used": 2,
            "tool_results": [],
            "plan": [{"action": "investigate", "description": "Explore", "completed": True}],
            "verification": {},
            "success": True,
        }
        output = format_agent_result(result, verbose=True)
        assert "task-1" in output
        assert "Plan:" in output

    def test_format_verbose_includes_tool_results(self):
        result = {
            "task_id": "task-1",
            "status": "COMPLETED",
            "iterations": 3,
            "tools_used": 2,
            "tool_results": [{"tool": "read_file", "success": True, "output": "file content"}],
            "plan": [],
            "verification": {},
            "success": True,
        }
        output = format_agent_result(result, verbose=True)
        assert "read_file" in output


class TestCleanAgentOutput:
    """Tests for clean agent output display."""

    def test_display_agent_result_success(self):
        repl = make_repl()

        result = {
            "success": True,
            "status": "COMPLETED",
            "tool_results": [{"tool": "write_file", "success": True}],
            "verification": {"test_results": {"passed": True, "total": 5}},
            "final_response": "Task done",
        }

        with patch.object(repl, '_stop_spinner'):
            with patch.object(repl, '_print') as mock_print:
                repl._display_agent_result(result)

        assert mock_print.called

    def test_display_agent_result_failure(self):
        repl = make_repl()

        result = {
            "success": False,
            "status": "FAILED",
            "tool_results": [],
            "verification": {},
            "error": "No model provider available",
            "final_response": "",
        }

        with patch.object(repl, '_stop_spinner'):
            with patch.object(repl, '_print') as mock_print:
                repl._display_agent_result(result)

        assert mock_print.called

    def test_display_agent_result_verbose(self):
        repl = make_repl()
        repl.verbose = True

        result = {
            "success": True,
            "status": "COMPLETED",
            "tool_results": [],
            "verification": {},
            "task_id": "task-test",
            "iterations": 3,
            "tools_used": 2,
        }

        with patch.object(repl, '_stop_spinner'), \
             patch.object(repl, '_print'):
            repl._display_agent_result(result)


class TestCleanFailedAgentOutput:
    """Tests for clean failed agent output display."""

    def test_display_agent_error(self):
        repl = make_repl()

        with patch.object(repl, '_stop_spinner'):
            with patch.object(repl, '_print') as mock_print:
                repl._display_agent_error("No model provider available.")

        assert mock_print.called

    def test_display_agent_error_no_traceback(self):
        repl = make_repl()

        with patch.object(repl, '_stop_spinner'):
            with patch.object(repl, '_print') as mock_print:
                repl._display_agent_error("No model provider available.")

        called_texts = []
        for call in mock_print.call_args_list:
            if call[0]:
                called_texts.append(str(call[0][0]))
        full_output = " ".join(called_texts)
        assert "Traceback" not in full_output
        assert "Agent failed" in full_output


class TestNoTracebacksInNormalMode:
    """Tests that tracebacks are not shown in normal (non-verbose) mode."""

    def test_run_no_traceback_on_error(self):
        repl = make_repl()
        repl.verbose = False

        call_count = [0]
        def fake_read_input():
            call_count[0] += 1
            if call_count[0] == 1:
                return "/help"
            return "/exit"

        with patch.object(repl, '_print_header'), \
             patch.object(repl, '_print_startup_info'), \
             patch.object(repl, '_stop_spinner'):
            repl._read_input = fake_read_input
            with patch.object(repl, '_print'):
                result = repl.run()

        assert result == 0


class TestCommandGroups:
    """Tests for command group structure used by autocomplete."""

    def test_groups_have_categories(self):
        group_names = [g["name"] for g in _COMMAND_GROUPS]
        assert "Agent" in group_names
        assert "Models" in group_names
        assert "System" in group_names

    def test_all_required_commands_present(self):
        all_names = set()
        for grp in _COMMAND_GROUPS:
            for cmd, name, desc in grp["commands"]:
                all_names.add(name)
        for required in ["agent", "project", "model", "providers", "models",
                         "memory", "skills", "session", "config", "tools",
                         "help", "exit", "clear"]:
            assert required in all_names, f"Missing command: {required}"

    def test_each_command_has_description(self):
        for grp in _COMMAND_GROUPS:
            for cmd, name, desc in grp["commands"]:
                assert desc and len(desc) > 5
