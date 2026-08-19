"""
Tests for ToolManager — the sole owner of tool execution.

These tests verify:
- ToolManager executes all tool types (filesystem, shell, git, test/build/format)
- HermesRuntime does NOT duplicate any of these implementations
- Tool failures return structured ToolResult, not exceptions
"""

import time

from agentcore.runtimes.base import (
    FinishReason,
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
    ToolResult,
)
from agentcore.runtimes.hermes import HermesRuntime
from agentcore.tools import ToolManager


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
        tc = ToolCall(
            tool="write_file", arguments={"path": "output.txt", "content": "written content"}
        )
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
        assert not hasattr(rt, "execute_tool"), (
            "HermesRuntime must not implement execute_tool — that's ToolManager's job"
        )

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
        assert not hasattr(rt, "shell"), (
            "HermesRuntime must not implement shell() — that's ToolManager's job"
        )

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

    def test_hermes_runtime_capabilities_standardized_keys(self):
        """Hermes capabilities must include standardized capability keys."""
        rt = HermesRuntime()
        caps = rt.capabilities()
        assert caps["text_generation"] is True
        assert caps["tool_calls"] is False
        assert caps["external_tool_execution"] is False
        assert caps["streaming"] is False
        assert caps["cancellation"] is True


class TestToolManagerTimeouts:
    """ToolManager enforces configurable per-tool timeouts."""

    def test_successful_tool_within_timeout(self, tmp_path):
        """A tool that completes within the timeout should succeed."""
        tm = ToolManager(project_path=tmp_path, tool_timeout=5)
        tc = ToolCall(tool="read_file", arguments={"path": "hello.txt"})
        (tmp_path / "hello.txt").write_text("fast")
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert result.exit_code == 0
        assert "fast" in result.output

    def test_timeout_failure_returns_structured_result(self, tmp_path):
        """A tool exceeding the timeout should return a structured ToolResult failure."""

        def slow_handler(args, work_dir, start):
            time.sleep(10)
            return ToolResult(success=True, tool="slow", output="done")

        tm = ToolManager(project_path=tmp_path, tool_timeout=1)
        tm.register_tool("slow_tool", slow_handler)
        tc = ToolCall(tool="slow_tool", arguments={})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is False
        assert result.exit_code == 124
        assert "timed out" in result.error.lower()
        assert result.tool == "slow_tool"

    def test_disabled_timeout_allows_slow_tool(self, tmp_path):
        """With tool_timeout=None, a slow tool should complete normally."""

        def slow_handler(args, work_dir, start):
            time.sleep(0.5)
            return ToolResult(success=True, tool="slow", output="done")

        tm = ToolManager(project_path=tmp_path, tool_timeout=None)
        tm.register_tool("slow_tool", slow_handler)
        tc = ToolCall(tool="slow_tool", arguments={})
        result = tm.execute(tc, cwd=tmp_path)

        assert result.success is True
        assert result.output == "done"

    def test_timeout_propagates_through_agent(self, tmp_path):
        """Agent should receive timeout ToolResult without crashing."""
        from agentcore import Agent, AgentConfig
        from agentcore.memory import InMemoryBackend, MemoryManager
        from agentcore.runtimes.base import RuntimeAdapter, RuntimeResponse

        class TimeoutRuntime(RuntimeAdapter):
            def respond(self, context):
                return RuntimeResponse(
                    content="",
                    tool_calls=[ToolCall(tool="slow_tool", arguments={})],
                    finish_reason=FinishReason.TOOL_CALLS,
                )

            def capabilities(self):
                return {
                    "text_generation": True,
                    "tool_calls": True,
                    "external_tool_execution": True,
                    "streaming": False,
                    "cancellation": False,
                }

            def cancel(self):
                pass

            @property
            def default_model(self):
                return "timeout-model"

        def slow_handler(args, work_dir, start):
            time.sleep(10)
            return ToolResult(success=True, tool="slow_tool", output="done")

        runtime = TimeoutRuntime()
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=2,
            max_tool_calls=10,
            tool_timeout=1,
            enable_verification=False,
            max_replans=0,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        agent._tool_manager.register_tool("slow_tool", slow_handler)

        result = agent.execute("Run slow tool")

        assert result["task"]["current_state"] == "FAILED"
        assert result["tools_used"] >= 1


# ─────────────────── Shell Contract & Subprocess Cancellation ──────────


class TestShellContract:
    """shell() is a shell-interpreted command tool."""

    def test_simple_command_success(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        result = tm.shell("echo hello")
        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_command_with_spaces_in_argument(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        result = tm.shell('echo "hello world"')
        assert result.success is True
        assert "hello world" in result.output

    def test_command_failure_returns_nonzero_exit(self, tmp_path):
        tm = ToolManager(project_path=tmp_path)
        result = tm.shell("false")
        assert result.success is False
        assert result.exit_code != 0

    def test_timeout_cancels_subprocess(self, tmp_path):
        """A timed-out shell command must be actually terminated."""
        tm = ToolManager(project_path=tmp_path)
        result = tm.shell("sleep 60", timeout=2)
        assert result.success is False
        assert result.exit_code == 124
        assert "timed out" in result.error.lower()
        assert tm._active_process is None

    def test_cancel_in_flight_kills_active_subprocess(self, tmp_path):
        """cancel_in_flight() must terminate an active shell subprocess."""
        tm = ToolManager(project_path=tmp_path)
        import threading

        started = threading.Event()
        finished = threading.Event()

        def run_sleep():
            started.set()
            res = tm.shell("sleep 60", timeout=60)
            finished.set()
            return res

        thread = threading.Thread(target=run_sleep)
        thread.start()
        started.wait(timeout=5)
        for _ in range(50):
            if tm._active_process is not None:
                break
            time.sleep(0.1)
        assert tm._active_process is not None
        tm.cancel_in_flight()
        finished.wait(timeout=5)
        thread.join(timeout=5)
        assert tm._active_process is None
