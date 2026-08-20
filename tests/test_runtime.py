import pytest
from agentcore.runtimes.base import RuntimeAdapter, ToolCall, ToolResult


class TestToolCall:
    def test_tool_call_creation(self):
        call = ToolCall(
            tool="shell",
            arguments={"command": "echo test"},
            thought="Running a simple echo command"
        )
        
        assert call.tool == "shell"
        assert call.arguments == {"command": "echo test"}
        assert call.thought == "Running a simple echo command"

    def test_tool_call_dataclass(self):
        call = ToolCall(tool="read_file", arguments={"path": "/etc/hosts"})
        
        assert call.tool == "read_file"
        assert call.arguments["path"] == "/etc/hosts"

    def test_tool_call_to_dict(self):
        call = ToolCall(tool="shell", arguments={"command": "ls"}, thought="list files")
        data = call.to_dict()
        
        assert data["tool"] == "shell"
        assert data["arguments"]["command"] == "ls"
        assert data["thought"] == "list files"


class TestToolResult:
    def test_successful_result(self):
        result = ToolResult(
            success=True,
            tool="shell",
            stdout="hello\n",
            stderr="",
            exit_code=0,
            duration=0.1,
        )
        
        assert result.success == True
        assert result.exit_code == 0
        assert result.tool == "shell"

    def test_failed_result(self):
        result = ToolResult(
            success=False,
            tool="read_file",
            stdout="",
            stderr="File not found",
            exit_code=1,
            duration=0.05,
        )
        
        assert result.success == False
        assert result.exit_code == 1
        assert result.tool == "read_file"

    def test_to_dict(self):
        result = ToolResult(
            success=True,
            tool="shell",
            stdout="output",
            stderr="",
            exit_code=0,
            duration=0.1,
        )
        
        data = result.to_dict()
        
        assert data["success"] == True
        assert data["tool"] == "shell"
        assert data["stdout"] == "output"


class TestRuntimeAdapterInterface:
    def test_runtime_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            RuntimeAdapter()


class TestHermesAPI:
    def test_build_prompt_structure(self):
        from agentcore.runtimes.base import HermesAPI
        
        context = {
            "task": {
                "user_request": "Fix bug",
                "project": "test-project",
                "current_state": "ANALYZING",
            },
            "project_context": {"language": "python"},
            "memory": [{"content": "previous discussion"}],
            "skills": ["debugging"],
            "user_request": "Fix the crash",
        }
        
        prompt = HermesAPI.build_prompt(context)
        
        assert "Task:" in prompt
        assert "Fix bug" in prompt
        assert "test-project" in prompt


class TestHermesAPIWithEmptyContext:
    def test_empty_context(self):
        from agentcore.runtimes.base import HermesAPI
        
        prompt = HermesAPI.build_prompt({"user_request": "Do something"})
        
        assert "USER: Do something" in prompt