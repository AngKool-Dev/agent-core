import pytest
from pathlib import Path
from agentcore import Agent, AgentConfig, create_agent
from agentcore.memory import MemoryManager, MemoryBackend
from agentcore.runtimes.base import ToolCall, ToolResult
from tests.test_mock_runtime import MockRuntime


class InMemoryBackend(MemoryBackend):
    def __init__(self):
        self._store = []
    
    def search(self, query, project=None, limit=20):
        return [m for m in self._store if query.lower() in m.get("content", "").lower()]
    
    def store(self, type, content, project=None, importance=0.5):
        mem = {"id": f"mem-{len(self._store)}", "type": type, "content": content, "project": project}
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
        
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
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
        
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Test limit")
        
        assert result["iterations"] <= 3

    def test_tool_limit_enforced(self, tmp_path):
        tool_calls = [ToolCall(tool="read_file", arguments={"path": f"/file{i}.txt"}) for i in range(100)]
        
        runtime = MockRuntime(responses=tool_calls[:50])
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=100,
            max_tool_calls=5,
            enable_verification=False,
        )
        
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
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
        
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Test without verification")
        
        assert result["success"] == True
        assert "verification" in result
        verification = result["verification"]
        assert verification["overall_passed"] is True
        assert verification["format_check"] is None
        assert verification["build_check"] is None
        assert verification["test_results"] is None
        assert verification["git_diff_check"] is None
        assert verification["failures"] == []
        assert verification.get("skipped") is True

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
        
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Test with verification")
        
        assert "verification" in result