"""
Deterministic runtime for AgentCore integration testing.

Simulates a complete coding-agent lifecycle without external dependencies.
"""

from typing import Any

from agentcore.runtimes.base import FinishReason, RuntimeAdapter, RuntimeResponse, ToolCall


class DeterministicRuntime(RuntimeAdapter):
    """
    A deterministic fake runtime for integration testing.

    Drives a predefined sequence of responses, supporting:
    - Successful task completion
    - Tool calls
    - Tool failures
    - Runtime errors
    - Timeouts
    """

    def __init__(self, responses: list[Any] | None = None, fail_on_call: int | None = None):
        self._responses: list[RuntimeResponse] = []
        self._response_index = 0
        self._last_response: RuntimeResponse | None = None
        self._call_count = 0
        self._fail_on_call = fail_on_call

        for resp in responses or []:
            self._responses.append(self._coerce(resp))

    def _coerce(self, resp: Any) -> RuntimeResponse:
        if isinstance(resp, RuntimeResponse):
            return resp
        if isinstance(resp, ToolCall):
            return RuntimeResponse(
                content="",
                tool_calls=[resp],
                finish_reason=FinishReason.TOOL_CALLS,
            )
        if isinstance(resp, dict):
            if "error" in resp:
                return RuntimeResponse(
                    content="",
                    tool_calls=[],
                    finish_reason=FinishReason.ERROR,
                    metadata={"error": resp["error"]},
                )
            if "tool_call" in resp:
                return RuntimeResponse(
                    content=resp.get("response", ""),
                    tool_calls=[resp["tool_call"]],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            if "timeout" in resp:
                return RuntimeResponse(
                    content="",
                    tool_calls=[],
                    finish_reason=FinishReason.TIMEOUT,
                    metadata={"timeout": True},
                )
            return RuntimeResponse(content=str(resp), finish_reason=FinishReason.STOP)
        text = str(resp) if not isinstance(resp, str) else resp
        return RuntimeResponse(content=text, finish_reason=FinishReason.STOP)

    def respond(self, context: dict[str, Any]) -> RuntimeResponse:
        self._call_count += 1
        if self._fail_on_call is not None and self._call_count >= self._fail_on_call:
            raise RuntimeError("Simulated runtime failure")
        if not self._responses:
            return RuntimeResponse(
                content="Task completed",
                finish_reason=FinishReason.STOP,
            )
        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
        else:
            response = RuntimeResponse(
                content=self._last_response.content if self._last_response else "",
                tool_calls=[],
                finish_reason=FinishReason.STOP,
            )
        self._last_response = response
        return response

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "deterministic",
            "text_generation": True,
            "tool_calls": True,
            "external_tool_execution": True,
            "streaming": False,
            "cancellation": False,
        }

    def cancel(self) -> None:
        pass

    @property
    def default_model(self) -> str | None:
        return "deterministic-model"

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset(self) -> None:
        self._response_index = 0
        self._call_count = 0
        self._last_response = None


def bug_fix_lifecycle() -> list[Any]:
    """
    Return a sequence of responses simulating a successful bug fix.

    Sequence:
    1. Investigate (tool call)
    2. Analyze (tool call)
    3. Implement fix (tool call)
    4. Verify (text response)
    """
    return [
        ToolCall(tool="read_file", arguments={"path": "src/main.py"}),
        "The bug is in the error handling logic. Let me implement a fix.",
        ToolCall(tool="write_file", arguments={"path": "src/main.py", "content": "fixed"}),
        "Fix applied. Running verification...",
        "COMPLETE",
    ]


def multi_tool_lifecycle() -> list[Any]:
    """
    Return a sequence with multiple tool calls in one iteration.
    """
    return [
        [
            ToolCall(tool="read_file", arguments={"path": "a.py"}),
            ToolCall(tool="read_file", arguments={"path": "b.py"}),
        ],
        "Analysis complete. Implementing fix.",
        ToolCall(tool="write_file", arguments={"path": "a.py", "content": "fixed"}),
        "COMPLETE",
    ]


def tool_failure_lifecycle() -> list[Any]:
    """
    Return a sequence with a tool failure followed by recovery.
    """
    return [
        ToolCall(tool="read_file", arguments={"path": "missing.py"}),
        "The file is missing. Let me create it.",
        ToolCall(tool="write_file", arguments={"path": "missing.py", "content": "created"}),
        "COMPLETE",
    ]


def verification_failure_lifecycle() -> list[Any]:
    """
    Return a sequence that triggers verification failure and replanning.
    """
    return [
        ToolCall(tool="write_file", arguments={"path": "src/main.py", "content": "incomplete"}),
        "Implementation done.",
    ]


def runtime_failure_lifecycle() -> list[Any]:
    """
    Return a sequence for runtime failure testing.
    Use with fail_on_call=1 in tests.
    """
    return ["This should not be reached"]


def timeout_lifecycle() -> list[Any]:
    """
    Return a sequence that triggers a timeout.
    """
    return [{"timeout": True}]
