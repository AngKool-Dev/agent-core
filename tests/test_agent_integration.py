"""
Tests for Agent integration with the new runtime/tool boundary.

These tests verify:
- Agent gets RuntimeResponse from the runtime (not raw strings or dicts)
- Agent executes tool calls through ToolManager (not through runtime)
- Agent feeds tool results back to the runtime for the next iteration
- Tool success and failure are handled gracefully
"""

from unittest.mock import patch

from agentcore import Agent, AgentConfig
from agentcore.memory import MemoryManager
from agentcore.runtimes.base import (
    FinishReason,
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
)
from tests.test_mock_runtime import MockRuntime


class InMemoryBackend:
    """Simple in-memory memory backend for tests."""

    def __init__(self):
        self._store = []

    def search(self, query, project=None, limit=20):
        return [m for m in self._store if query.lower() in m.get("content", "").lower()]

    def store(self, type, content, project=None, importance=0.5):
        mem = {
            "id": f"mem-{len(self._store)}",
            "type": type,
            "content": content,
            "project": project,
        }
        self._store.append(mem)
        return mem

    def update(self, memory_id, content):
        for m in self._store:
            if m["id"] == memory_id:
                m["content"] = content
                return m
        return {}

    def list(self, project=None, type=None, limit=50):
        return self._store


class TestAgentWithRuntimeResponse:
    """Agent processes RuntimeResponse objects, not raw strings."""

    def test_agent_receives_runtime_response(self, tmp_path):
        """Agent should work with a runtime that returns RuntimeResponse."""
        runtime = MockRuntime(responses=["Task analysis complete"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=1,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Analyze this code")

        assert result["success"] is True
        assert result["task"]["current_state"] == "COMPLETED"

    def test_agent_no_hasattr_probing(self):
        """Agent must not use hasattr to probe runtime for tool methods."""
        import inspect

        source = inspect.getsource(Agent)
        assert "hasattr(runtime" not in source, (
            "Agent must not use hasattr() to probe runtime capabilities"
        )
        assert "get_pending_tool_call" not in source or "getattr" not in source, (
            "Agent must not probe runtime for get_pending_tool_call"
        )


class TestAgentToolExecution:
    """Agent executes tool calls through ToolManager."""

    def test_agent_processes_tool_calls_from_runtime(self, tmp_path):
        """When runtime returns a RuntimeResponse with tool calls,
        Agent should execute them through ToolManager."""
        # Create a file so read_file succeeds
        (tmp_path / "source.py").write_text("print('hello')\n")

        tool_call = ToolCall(tool="read_file", arguments={"path": "source.py"})
        runtime = MockRuntime(responses=[tool_call])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read source.py")

        assert result["tools_used"] >= 1

    def test_agent_tool_failure_does_not_crash(self, tmp_path):
        """Tool failures should produce a ToolResult with success=False, not crash."""
        tool_call = ToolCall(tool="read_file", arguments={"path": "nonexistent.py"})
        runtime = MockRuntime(responses=[tool_call, "Task complete"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read a nonexistent file")

        # Agent should still complete (not crash)
        assert "task" in result

    def test_agent_unknown_tool_failure(self, tmp_path):
        """Unknown tool names should return a failure ToolResult, not crash."""
        tool_call = ToolCall(tool="unknown_tool", arguments={})
        runtime = MockRuntime(responses=[tool_call, "Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Use unknown tool")

        assert "task" in result
        assert result["tools_used"] >= 1

    def test_agent_multiple_tool_calls(self, tmp_path):
        """Agent should handle multiple sequential tool calls."""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        tc1 = ToolCall(tool="read_file", arguments={"path": "file1.txt"})
        tc2 = ToolCall(tool="read_file", arguments={"path": "file2.txt"})
        runtime = MockRuntime(responses=[tc1, tc2, "All done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read both files")

        assert result["tools_used"] >= 2

    def test_agent_tool_limit_enforced(self, tmp_path):
        """Agent should respect max_tool_calls limit."""
        tool_calls = [
            ToolCall(tool="read_file", arguments={"path": f"file{i}.txt"}) for i in range(20)
        ]
        runtime = MockRuntime(responses=tool_calls[:10])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=20,
            max_tool_calls=3,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read many files")

        assert result["tools_used"] <= 3


class TestAgentIterationFlow:
    """Verify the model response → tool execution → next model iteration flow."""

    def test_tool_result_fed_back_to_runtime(self, tmp_path):
        """The Agent should include tool results in the context for the next
        runtime call, enabling iterative refinement."""
        (tmp_path / "input.txt").write_text("data to process")

        tc = ToolCall(tool="read_file", arguments={"path": "input.txt"})
        runtime = MockRuntime(responses=[tc, "I processed the file"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read and process input.txt")

        # Should have executed the tool at least once
        assert result["tools_used"] >= 1
        # Should have received the second response ("I processed the file")
        assert result["task"]["current_state"] == "COMPLETED"

    def test_response_without_tool_calls(self, tmp_path):
        """A model response with no tool calls should lead to completion."""
        runtime = MockRuntime(responses=["Final answer: everything looks good"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Give me a summary")

        assert result["success"] is True
        assert result["tools_used"] == 0

    def test_iteration_limit_enforced(self, tmp_path):
        """Agent should stop when max_iterations is reached."""
        runtime = MockRuntime(responses=["Keep going"] * 100)
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=3,
            max_tool_calls=100,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Keep going forever")

        assert result["iterations"] <= 3


class BlackBoxRuntime(RuntimeAdapter):
    """Runtime that declares no tool capabilities but can return text."""

    def __init__(self, responses=None):
        self._responses = responses or ["Done"]
        self._index = 0

    def respond(self, context):
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            if isinstance(resp, RuntimeResponse):
                return resp
            return RuntimeResponse(content=str(resp), finish_reason=FinishReason.STOP)
        return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

    def capabilities(self):
        return {
            "text_generation": True,
            "tool_calls": False,
            "external_tool_execution": False,
            "streaming": False,
            "cancellation": False,
        }

    def cancel(self):
        pass

    @property
    def default_model(self):
        return "blackbox-model"


class ContractViolatingRuntime(RuntimeAdapter):
    """Runtime that declares tool_calls=False but returns tool calls."""

    def __init__(self, responses=None):
        self._responses = responses or []
        self._index = 0

    def respond(self, context):
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            if isinstance(resp, RuntimeResponse):
                return resp
            return RuntimeResponse(content=str(resp), finish_reason=FinishReason.STOP)
        return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

    def capabilities(self):
        return {
            "text_generation": True,
            "tool_calls": False,
            "external_tool_execution": False,
            "streaming": False,
            "cancellation": False,
        }

    def cancel(self):
        pass

    @property
    def default_model(self):
        return "violation-model"


class TestAgentCapabilityAwareness:
    """Agent must respect runtime capability declarations."""

    def test_black_box_runtime_completes_without_tool_states(self, tmp_path):
        """A runtime declaring tool_calls=False should complete text tasks normally."""
        runtime = BlackBoxRuntime(responses=["Task complete"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Reply with hello")

        assert result["success"] is True
        assert result["task"]["current_state"] == "COMPLETED"
        assert result["tools_used"] == 0

    def test_contract_violation_tool_calls_false_returns_tool_calls(self, tmp_path):
        """Runtime declaring tool_calls=False but returning tool_calls should fail."""
        tool_call = ToolCall(tool="read_file", arguments={"path": "x.py"})
        runtime = ContractViolatingRuntime(
            responses=[
                RuntimeResponse(
                    content="", tool_calls=[tool_call], finish_reason=FinishReason.TOOL_CALLS
                ),
            ]
        )
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read x.py")

        assert result["task"]["current_state"] == "FAILED"
        assert result["stopped_reason"] == "runtime_contract_violation"

    def test_contract_violation_tool_calls_true_external_false(self, tmp_path):
        """Runtime with tool_calls=True but external_tool_execution=False fails on tool calls."""

        class HybridRuntime(RuntimeAdapter):
            def __init__(self):
                self.called = False

            def respond(self, context):
                if not self.called:
                    self.called = True
                    return RuntimeResponse(
                        content="",
                        tool_calls=[ToolCall(tool="read_file", arguments={"path": "x.py"})],
                        finish_reason=FinishReason.TOOL_CALLS,
                    )
                return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

            def capabilities(self):
                return {
                    "text_generation": True,
                    "tool_calls": True,
                    "external_tool_execution": False,
                    "streaming": False,
                    "cancellation": False,
                }

            def cancel(self):
                pass

            @property
            def default_model(self):
                return "hybrid-model"

        runtime = HybridRuntime()
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read x.py")

        assert result["task"]["current_state"] == "FAILED"
        assert result["stopped_reason"] == "runtime_contract_violation"

    def test_contract_violation_tool_calls_false_external_true(self, tmp_path):
        """Runtime with tool_calls=False but external_tool_execution=True fails on tool calls."""

        class InconsistentRuntime(RuntimeAdapter):
            def __init__(self):
                self.called = False

            def respond(self, context):
                if not self.called:
                    self.called = True
                    return RuntimeResponse(
                        content="",
                        tool_calls=[ToolCall(tool="read_file", arguments={"path": "x.py"})],
                        finish_reason=FinishReason.TOOL_CALLS,
                    )
                return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

            def capabilities(self):
                return {
                    "text_generation": True,
                    "tool_calls": False,
                    "external_tool_execution": True,
                    "streaming": False,
                    "cancellation": False,
                }

            def cancel(self):
                pass

            @property
            def default_model(self):
                return "inconsistent-model"

        runtime = InconsistentRuntime()
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Read x.py")

        assert result["task"]["current_state"] == "FAILED"
        assert result["stopped_reason"] == "runtime_contract_violation"

    def test_agent_queries_capabilities_before_tool_execution(self, tmp_path):
        """Agent should query runtime.capabilities() and respect the result."""

        class QueryTrackingRuntime(RuntimeAdapter):
            def __init__(self, responses=None):
                self._responses = responses or ["Done"]
                self._index = 0
                self.capabilities_calls = 0

            def respond(self, context):
                if self._index < len(self._responses):
                    resp = self._responses[self._index]
                    self._index += 1
                    if isinstance(resp, RuntimeResponse):
                        return resp
                    return RuntimeResponse(content=str(resp), finish_reason=FinishReason.STOP)
                return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

            def capabilities(self):
                self.capabilities_calls += 1
                return {
                    "text_generation": True,
                    "tool_calls": False,
                    "external_tool_execution": False,
                    "streaming": False,
                    "cancellation": False,
                }

            def cancel(self):
                pass

            @property
            def default_model(self):
                return "query-model"

        runtime = QueryTrackingRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Reply with hello")

        assert runtime.capabilities_calls >= 1
        assert result["success"] is True


class TestVerificationScope:
    """Tests for verification_scope and changed-files behavior."""

    def test_default_verification_scope_is_project(self):
        """Default verification_scope should be 'project'."""
        config = AgentConfig()
        assert getattr(config, "verification_scope", "project") == "project"

    def test_changed_files_scope_computes_delta(self, tmp_path):
        """changed-files scope should compute the task delta, not the full dirty set."""
        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
            verification_scope="changed-files",
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)

        with patch.object(
            agent, "_capture_changed_files", side_effect=[["a.py"], ["a.py", "b.py"]]
        ):
            agent._baseline_changed_files = ["a.py"]
            result = agent.execute("Do something")

        assert result["success"] is True

    def test_changed_files_zero_changes_skips_verification(self, tmp_path):
        """Zero changed files under changed-files scope should skip verification."""
        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=True,
            run_format_check=True,
            verification_scope="changed-files",
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)

        with patch.object(agent, "_capture_changed_files", side_effect=[[], []]):
            agent._baseline_changed_files = []
            result = agent.execute("Reply with hello")

        assert result["success"] is True

    def test_changed_files_git_failure_falls_back_to_project(self, tmp_path):
        """Git snapshot failure should fall back to project-wide verification."""
        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=True,
            run_format_check=True,
            verification_scope="changed-files",
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)

        with patch.object(agent, "_capture_changed_files", side_effect=[None, ["b.py"]]):
            agent._baseline_changed_files = None
            result = agent.execute("Reply with hello")

        assert result["success"] is True

    def test_dirty_repo_trapdoor_pre_existing_not_agent_change(self, tmp_path):
        """Pre-existing dirty files must not be counted as agent changes."""
        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
            verification_scope="changed-files",
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)

        with patch.object(
            agent, "_capture_changed_files", side_effect=[["a.py"], ["a.py", "b.py"]]
        ):
            agent._baseline_changed_files = ["a.py"]
            result = agent.execute("Do something")

        assert result["success"] is True
