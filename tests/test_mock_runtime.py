import pytest
from typing import Optional, List, Any, Dict
from agentcore.runtimes.base import RuntimeAdapter, ToolCall, ToolResult


class MockRuntime(RuntimeAdapter):
    def __init__(self, responses: Optional[List[Any]] = None, tool_calls: Optional[List[ToolCall]] = None):
        self._responses = responses or []
        self._tool_calls = tool_calls or []
        self._response_index = 0
        self._tool_call_index = 0
        self._complete = False
        self._response_text = ""

    def respond(self, context: Dict[str, Any]) -> Any:
        if not self._responses:
            self._complete = True
            return {"response": "Task completed", "complete": True}
        
        response = self._responses[self._response_index]
        self._response_index += 1
        
        if isinstance(response, ToolCall):
            self._tool_call_index += 1
            self._response_text = f"TOOL_CALL: {response.tool} {{{{ {self._format_args(response.arguments)} }}}}"
            return {"tool_call": response, "complete": False}
        else:
            self._complete = True
            self._response_text = str(response) if not isinstance(response, dict) else response.get("response", "")
            return {"response": self._response_text, "complete": True}

    def _format_args(self, args: Dict[str, Any]) -> str:
        return ", ".join(f'"{k}": "{v}"' for k, v in args.items())

    def get_response_text(self) -> str:
        return self._response_text

    def is_complete(self) -> bool:
        return self._complete

    def get_pending_tool_call(self) -> Optional[ToolCall]:
        if self._tool_calls and self._tool_call_index <= len(self._tool_calls):
            return self._tool_calls[self._tool_call_index - 1]
        return None

    def execute_tool(self, tool_call: ToolCall, cwd=None) -> ToolResult:
        if tool_call.tool == "read_file":
            path = tool_call.arguments.get("path", "")
            content = f"Mock content of {path}\nLine 2\nLine 3\n"
            return ToolResult(
                success=True,
                tool=tool_call.tool,
                stdout=content,
                duration=0.01,
            )
        elif tool_call.tool == "run_command":
            cmd = tool_call.arguments.get("command", "")
            if "echo" in cmd:
                return ToolResult(
                    success=True,
                    tool=tool_call.tool,
                    stdout="mock output\n",
                    duration=0.01,
                )
            return ToolResult(
                success=True,
                tool=tool_call.tool,
                stdout="",
                stderr="",
                exit_code=0,
                duration=0.01,
            )
        return ToolResult(
            success=False,
            tool=tool_call.tool,
            error=f"Unknown tool {tool_call.tool}",
            duration=0.01,
        )


class TestMockRuntime:
    def test_mock_completes_immediately(self):
        runtime = MockRuntime(responses=["Done!"])
        result = runtime.respond({})
        
        assert result.get("complete") == True
        assert "Done" in result.get("response", "")

    def test_mock_handles_tool_call(self):
        runtime = MockRuntime(
            responses=[ToolCall(tool="read_file", arguments={"path": "/test/file.txt"})]
        )
        result = runtime.respond({})
        
        assert "tool_call" in result
        assert result["tool_call"].tool == "read_file"

    def test_mock_executes_tool(self):
        runtime = MockRuntime()
        tool_call = ToolCall(tool="read_file", arguments={"path": "/test.txt"})
        
        result = runtime.execute_tool(tool_call)
        
        assert result.success == True
        assert result.tool == "read_file"

    def test_mock_detects_completion(self):
        runtime = MockRuntime()
        
        runtime.respond({})
        assert runtime.is_complete() == True