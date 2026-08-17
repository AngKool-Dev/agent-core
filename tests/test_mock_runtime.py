import pytest
from typing import Optional, List, Any, Dict
from agentcore.runtimes.base import (
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
    ToolResult,
    FinishReason,
)
from agentcore.tools import ToolManager
from pathlib import Path


class MockRuntime(RuntimeAdapter):
    """
    Mock runtime for testing that conforms to the same RuntimeAdapter
    contract as HermesRuntime.

    A test should be able to swap MockRuntime in place of HermesRuntime
    without changing AgentCore behavior — both produce RuntimeResponse.
    """

    def __init__(
        self,
        responses: Optional[List[Any]] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ):
        self._responses: List[RuntimeResponse] = []
        self._response_index = 0
        self._tool_call_index = 0
        self._last_response: Optional[RuntimeResponse] = None

        # Convert legacy response formats (strings, dicts, ToolCalls) into RuntimeResponse
        for resp in responses or []:
            self._responses.append(self._coerce(resp))

        # Also accept an explicit list of ToolCall objects
        for tc in tool_calls or []:
            self._responses.append(RuntimeResponse(
                content="",
                tool_calls=[tc],
                finish_reason=FinishReason.TOOL_CALLS,
            ))

    def _coerce(self, resp: Any) -> RuntimeResponse:
        """Convert various input formats into a RuntimeResponse."""
        if isinstance(resp, RuntimeResponse):
            return resp
        if isinstance(resp, ToolCall):
            return RuntimeResponse(
                content="",
                tool_calls=[resp],
                finish_reason=FinishReason.TOOL_CALLS,
            )
        if isinstance(resp, dict):
            if "tool_call" in resp:
                return RuntimeResponse(
                    content=resp.get("response", ""),
                    tool_calls=[resp["tool_call"]],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            if "response" in resp:
                complete = resp.get("complete", True)
                return RuntimeResponse(
                    content=resp["response"],
                    tool_calls=[],
                    finish_reason=FinishReason.STOP if complete else FinishReason.STOP,
                )
            # Fallback: stringify
            return RuntimeResponse(content=str(resp), finish_reason=FinishReason.STOP)
        # String or anything else
        text = str(resp) if not isinstance(resp, str) else resp
        return RuntimeResponse(content=text, finish_reason=FinishReason.STOP)

    def respond(self, context: Dict[str, Any]) -> RuntimeResponse:
        if not self._responses:
            response = RuntimeResponse(
                content="Task completed",
                tool_calls=[],
                finish_reason=FinishReason.STOP,
            )
            self._last_response = response
            return response

        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
        else:
            # Exhausted pre-set responses; stay stopped
            response = RuntimeResponse(
                content=self._last_response.content if self._last_response else "",
                tool_calls=[],
                finish_reason=FinishReason.STOP,
            )

        self._last_response = response
        return response

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "mock",
            "supports_tool_calls": True,
            "supports_streaming": False,
        }

    def cancel(self) -> None:
        pass

    @property
    def default_model(self) -> Optional[str]:
        return "mock-model"

    # --- Backward-compatible helpers ---
    def get_response_text(self) -> str:
        if self._last_response:
            return self._last_response.content
        return ""

    def is_complete(self) -> bool:
        if self._last_response:
            return self._last_response.is_complete
        return False

    def get_pending_tool_calls(self) -> List[ToolCall]:
        if self._last_response:
            return self._last_response.tool_calls
        return []


class TestMockRuntime:
    def test_mock_completes_immediately(self):
        runtime = MockRuntime(responses=["Done!"])
        result = runtime.respond({})

        assert isinstance(result, RuntimeResponse)
        assert result.finish_reason == FinishReason.STOP
        assert "Done" in result.content

    def test_mock_handles_tool_call(self):
        runtime = MockRuntime(
            responses=[ToolCall(tool="read_file", arguments={"path": "/test/file.txt"})]
        )
        result = runtime.respond({})

        assert isinstance(result, RuntimeResponse)
        assert result.finish_reason == FinishReason.TOOL_CALLS
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool == "read_file"

    def test_mock_executes_tool(self, tmp_path):
        # Create the test file so read_file succeeds
        (tmp_path / "test.txt").write_text("Mock content of test.txt\nLine 2\nLine 3\n")

        runtime = MockRuntime()
        tool_call = ToolCall(tool="read_file", arguments={"path": "test.txt"})

        tm = ToolManager(project_path=tmp_path)
        result = tm.execute(tool_call, cwd=tmp_path)

        assert result.success is True
        assert result.tool == "read_file"
        assert "Mock content" in result.output

    def test_mock_detects_completion(self):
        runtime = MockRuntime()

        runtime.respond({})
        assert runtime.is_complete() is True

    def test_mock_returns_runtime_response(self):
        runtime = MockRuntime(responses=["Hello world"])
        result = runtime.respond({})

        assert isinstance(result, RuntimeResponse)
        assert hasattr(result, "content")
        assert hasattr(result, "tool_calls")
        assert hasattr(result, "finish_reason")

    def test_mock_conforms_to_runtime_adapter(self):
        """MockRuntime must be a proper RuntimeAdapter subclass."""
        runtime = MockRuntime(responses=["test"])
        assert isinstance(runtime, RuntimeAdapter)

    def test_mock_capabilities(self):
        runtime = MockRuntime(responses=["test"])
        caps = runtime.capabilities()
        assert "adapter" in caps
        assert caps["adapter"] == "mock"

    def test_mock_cancel_noop(self):
        """cancel() must not raise."""
        runtime = MockRuntime(responses=["test"])
        runtime.cancel()  # should be a no-op

    def test_mock_exhaustion_returns_complete(self):
        runtime = MockRuntime(responses=["first"])
        runtime.respond({})  # consumes "first"
        result = runtime.respond({})  # exhausted

        assert result.finish_reason == FinishReason.STOP
