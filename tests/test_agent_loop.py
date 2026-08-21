from agentcore import Agent, AgentConfig
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.runtimes.base import ToolCall, ToolResult
from tests.test_mock_runtime import MockRuntime


class InMemoryBackend(MemoryBackend):
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


class TestIterativeAgentLoop:
    def test_single_step_execution(self, tmp_path):
        runtime = MockRuntime(responses=["Task analysis complete"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=1,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Analyze this code")

        assert result["success"] == True
        assert result["task"]["current_state"] == "COMPLETED"

    def test_multi_iteration_execution(self):
        steps = [
            ToolCall(tool="read_file", arguments={"path": "/test.py"}),
            "Analysis complete",
        ]

        runtime = MockRuntime(responses=steps)
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config)
        result = agent.execute("Read and test")

        assert result["iterations"] >= 0

    def test_iteration_limit_enforced(self, tmp_path):
        runtime = MockRuntime(responses=["Response"] * 100)
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=3,
            max_tool_calls=5,
            enable_verification=False,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test limit")

        assert result["iterations"] <= 3

    def test_tool_limit_enforced(self, tmp_path):
        tool_calls = [
            ToolCall(tool="read_file", arguments={"path": f"/file{i}.txt"})
            for i in range(100)
        ]

        runtime = MockRuntime(responses=tool_calls[:50])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=100,
            max_tool_calls=5,
            enable_verification=False,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test tool limit")

        assert result["tools_used"] <= 5


class TestAgentWithMockRuntime:
    def test_verification_disabled(self, tmp_path):
        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            enable_verification=False,
            max_iterations=1,
            max_tool_calls=5,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test without verification")

        assert result["success"] == True

    def test_verification_enabled_with_failures(self, tmp_path):
        runtime = MockRuntime(responses=["Analysis done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            enable_verification=True,
            run_format_check=True,
            run_build_check=True,
            run_tests=True,
            max_iterations=1,
            max_tool_calls=10,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test with verification")

        assert "verification" in result


class TestAutonomousLoopRecovery:
    def test_cancellation_stops_loop(self, tmp_path):
        runtime = MockRuntime(responses=["Response"] * 100)
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=100,
            max_tool_calls=100,
            enable_verification=False,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )

        call_count = [0]

        def cancel_on_second(context):
            call_count[0] += 1
            if call_count[0] >= 2:
                agent.cancel()
            return {"complete": False, "response": "Working", "tool_calls": []}

        runtime.respond = cancel_on_second
        result = agent.execute("Test cancellation")

        assert result["status"] == "CANCELLED"
        assert result["stopped_reason"] == "user_cancellation"

    def test_consecutive_failures_stop_loop(self, tmp_path):
        failing_tool = ToolCall(tool="read_file", arguments={"path": "/missing.txt"})
        runtime = MockRuntime(
            responses=[failing_tool, failing_tool, failing_tool, "Done"]
        )
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            max_consecutive_failures=2,
            enable_verification=False,
        )

        def failing_execute(tool_call, cwd=None):
            return ToolResult(
                success=False,
                tool=tool_call.tool,
                error="File not found",
                exit_code=1,
            )

        runtime.execute_tool = failing_execute
        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test consecutive failures")

        assert result["status"] == "FAILED"
        assert result["stopped_reason"] == "consecutive_tool_failures"

    def test_no_progress_detection_stops_loop(self, tmp_path):
        tool_call = ToolCall(tool="read_file", arguments={"path": "/file.txt"})
        runtime = MockRuntime(responses=[tool_call, tool_call, tool_call, "Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            max_no_progress=2,
            enable_verification=False,
        )

        def same_tool_result(tool_call, cwd=None):
            return ToolResult(
                success=True,
                tool=tool_call.tool,
                stdout="content",
                exit_code=0,
            )

        runtime.execute_tool = same_tool_result
        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test no progress")

        assert result["status"] == "FAILED"
        assert result["stopped_reason"] == "no_progress"

    def test_timeout_stops_loop(self, tmp_path):
        runtime = MockRuntime(responses=["Response"] * 100)
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=100,
            max_tool_calls=100,
            max_runtime_seconds=0,
            enable_verification=False,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Test timeout")

        assert result["status"] == "TIMEOUT"
        assert result["stopped_reason"] == "timeout"

    def test_successful_task_completes(self, tmp_path):
        runtime = MockRuntime(responses=["Task complete"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Analyze this code")

        assert result["status"] == "COMPLETED"
        assert result["success"] is True


class TestAutonomousLoopObservations:
    def test_observations_recorded(self, tmp_path):
        tool_call = ToolCall(tool="read_file", arguments={"path": "/test.txt"})
        runtime = MockRuntime(responses=[tool_call, "Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        def success_execute(tool_call, cwd=None):
            return ToolResult(
                success=True,
                tool=tool_call.tool,
                stdout="file content",
                exit_code=0,
            )

        runtime.execute_tool = success_execute
        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Read file")

        assert len(result["observations"]) > 0
        assert "1 succeeded" in result["observations"][0]

    def test_failed_tools_in_observation(self, tmp_path):
        tool_call = ToolCall(tool="read_file", arguments={"path": "/missing.txt"})
        runtime = MockRuntime(responses=[tool_call, "Done"])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        def fail_execute(tool_call, cwd=None):
            return ToolResult(
                success=False,
                tool=tool_call.tool,
                error="File not found",
                exit_code=1,
            )

        runtime.execute_tool = fail_execute
        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path
        )
        result = agent.execute("Read missing file")

        assert len(result["observations"]) > 0
        assert "0 succeeded" in result["observations"][0]
        assert "File not found" in result["observations"][0]
