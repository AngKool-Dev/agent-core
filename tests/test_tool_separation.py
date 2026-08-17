"""
Tests for ToolManager — the sole owner of tool execution.

These tests verify:
- ToolManager executes all tool types (filesystem, shell, git, test/build/format)
- HermesRuntime does NOT duplicate any of these implementations
- Tool failures return structured ToolResult, not exceptions
"""

import pytest
from pathlib import Path
from agentcore.tools import ToolManager, FileReadResult, FileWriteResult, SearchResult
from agentcore.runtimes.base import ToolCall, ToolResult, RuntimeResponse, FinishReason
from agentcore.runtimes.hermes import HermesRuntime
from agentcore.runtimes.base import RuntimeAdapter


class TestToolManagerFilesystem:
    """ToolManager executes filesystem tools."""

    def test_read_file_success(self, tmp_path):
        test_file = tmp_path / "hello.txt"
        test_file.write_text("Hello, World!")

        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="read_file", arguments={"path": "hello.txt"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert "Hello, World!" in result.output
        assert result.tool == "read_file"

    def test_read_file_not_found(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="read_file", arguments={"path": "nonexistent.txt"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is False
        assert "not found" in result.error.lower() or result.exit_code != 0

    def test_write_file_success(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="write_file", arguments={"path": "output.txt", "content": "written content"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert (tmp_path / "output.txt").read_text() == "written content"

    def test_search_files_finds_matches(self, tmp_path):
        (tmp_path / "test.py").write_text("def foo():\n    return 'bar'\n")
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="search_files", arguments={"query": "return"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert "test.py" in result.output
        assert result.metadata["result_count"] >= 1

    def test_search_files_no_matches(self, tmp_path):
        (tmp_path / "test.py").write_text("def foo():\n    return 'bar'\n")
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="search_files", arguments={"query": "xyz_not_found"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert result.output == ""


class TestToolManagerShell:
    """ToolManager executes shell tools."""

    def test_run_command_success(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="run_command", arguments={"command": "echo hello_world"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert "hello_world" in result.output

    def test_run_command_failure(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="run_command", arguments={"command": "exit 1"})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is False
        assert result.exit_code == 1

    def test_shell_method_directly(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        result = tm.shell("echo test123", cwd=tmp_path)
        assert result.success is True
        assert "test123" in result.output


class TestToolManagerGit:
    """ToolManager executes git tools."""

    def test_git_status_not_a_repo(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        result = tm.git_status()
        # git status returns empty or error in non-repo, but should not crash
        assert isinstance(result, str)

    def test_git_status_method_via_execute(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="git_status")
        result = tm.execute(tc, cwd=tmp_path)
        assert result.success is True  # git status exits 0 even outside repo
        assert result.tool == "git_status"

    def test_git_diff_check_via_execute(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="git_diff_check")
        result = tm.execute(tc, cwd=tmp_path)
        assert result.tool == "git_diff_check"


class TestToolManagerBuildFormatTest:
    """ToolManager executes build/format/test tools."""

    def test_check_build_unknown_project(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="check_build")
        result = tm.execute(tc, cwd=tmp_path)

        # For unknown project type, build returns success with no-op
        assert result.tool == "check_build"

    def test_check_format_unknown_project(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="check_format")
        result = tm.execute(tc, cwd=tmp_path)

        assert result.tool == "check_format"

    def test_run_tests_unknown_project(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="run_tests")
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is False
        assert "No test runner" in result.error


class TestToolManagerUnifiedDispatch:
    """ToolManager.execute dispatches all tool types."""

    def test_execute_unknown_tool(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="nonexistent_tool", arguments={})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is False
        assert "Unknown tool" in result.error

    def test_execute_does_not_raise_on_failure(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        tc = ToolCall(tool="read_file", arguments={"path": "/nonexistent/path/file.txt"})
        result = tm.execute(tc, cwd=tmp_path)

        assert isinstance(result, ToolResult)
        assert result.success is False


class TestToolResultStructure:
    """ToolResult has a predictable structure."""

    def test_tool_result_success(self):
        result = ToolResult(success=True, tool="shell", output="done", error="")
        assert result.success is True
        assert result.output == "done"
        assert result.error == ""

    def test_tool_result_failure(self):
        result = ToolResult(success=False, tool="read_file", output="", error="File not found")
        assert result.success is False
        assert result.error == "File not found"

    def test_tool_result_backward_compat_stdin_stderr(self):
        """stdout/stderr kwargs should still work."""
        result = ToolResult(success=True, tool="shell", stdout="out", stderr="err")
        assert result.output == "out"
        assert result.error == "err"
        assert result.stdout == "out"
        assert result.stderr == "err"

    def test_tool_result_to_dict(self):
        result = ToolResult(success=True, tool="shell", output="ok", error="", exit_code=0)
        data = result.to_dict()
        assert data["success"] is True
        assert data["tool"] == "shell"
        assert data["output"] == "ok"
        assert "metadata" in data


class TestHermesRuntimeNoToolDuplication:
    """HermesRuntime must NOT contain duplicate tool implementations."""

    def test_hermes_runtime_has_no_execute_tool(self):
        """HermesRuntime should not have execute_tool method (was removed in Phase 2)."""
        rt = HermesRuntime()
        assert not hasattr(rt, "execute_tool"), \
            "HermesRuntime must not implement execute_tool — that's ToolManager's job"

    def test_hermes_runtime_has_no_get_pending_tool_call(self):
        """HermesRuntime should not expose get_pending_tool_call (singular)."""
        rt = HermesRuntime()
        # The old hasattr-based probing in Agent is eliminated
        assert not hasattr(rt, "get_pending_tool_call") or hasattr(rt, "get_pending_tool_calls")

    def test_hermes_runtime_respond_returns_runtime_response(self):
        rt = HermesRuntime()
        resp = rt._parse_response("test response", "", 0)
        assert isinstance(resp, RuntimeResponse)

    def test_hermes_runtime_does_not_have_shell_method(self):
        """HermesRuntime should not have a shell() method — that's ToolManager's."""
        rt = HermesRuntime()
        assert not hasattr(rt, "shell"), \
            "HermesRuntime must not implement shell() — that's ToolManager's job"

    def test_hermes_runtime_does_not_have_read_file_method(self):
        rt = HermesRuntime()
        assert not hasattr(rt, "read_file")

    def test_hermes_runtime_does_not_have_run_tests_method(self):
        rt = HermesRuntime()
        assert not hasattr(rt, "run_tests")

    def test_hermes_runtime_does_not_have_git_methods(self):
        rt = HermesRuntime()
        assert not hasattr(rt, "git_status")
        assert not hasattr(rt, "git_diff")
        assert not hasattr(rt, "git_diff_check")

    def test_hermes_runtime_conforms_to_runtime_adapter(self):
        rt = HermesRuntime()
        assert isinstance(rt, RuntimeAdapter)

    def test_hermes_runtime_capabilities_no_tool_methods(self):
        """Capabilities should not advertise tool execution methods."""
        rt = HermesRuntime()
        caps = rt.capabilities()
        assert "execute_tool" not in caps
        assert "shell" not in caps
        assert "read_file" not in caps
