from typing import Any

from .base import FinishReason, RuntimeAdapter, RuntimeResponse


class EchoRuntime(RuntimeAdapter):
    """
    A minimal runtime adapter that echoes back the user request.

    This demonstrates how a second, independent runtime can integrate with
    AgentCore without any changes to AgentCore's core logic. It is a
    tool-aware runtime: it returns ``tool_calls`` in its response and
    expects AgentCore to execute them via ``ToolManager``.

    Use this as a starting point for building adapters for other agents
    (Kilo, OpenCode, Claude Code, custom agents, etc.).
    """

    def __init__(self, model: str | None = None):
        self.model = model or "echo"
        self._call_count = 0

    def respond(self, context: dict[str, Any]) -> RuntimeResponse:
        self._call_count += 1
        user_request = context.get("user_request", "")

        return RuntimeResponse(
            content=f"Echo: {user_request}",
            tool_calls=[],
            finish_reason=FinishReason.STOP,
        )

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "echo",
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
        return self.model

    @property
    def call_count(self) -> int:
        return self._call_count


def create_echo_runtime(model: str | None = None) -> EchoRuntime:
    """Factory for the EchoRuntime, matching the Hermes factory pattern."""
    return EchoRuntime(model=model)
