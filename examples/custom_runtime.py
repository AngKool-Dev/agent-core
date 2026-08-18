"""
Custom runtime adapter example.

Demonstrates how to implement a RuntimeAdapter for a new model backend.
"""

from agentcore.runtimes.base import RuntimeAdapter, RuntimeResponse, ToolCall, FinishReason


class MyCustomRuntime(RuntimeAdapter):
    """
    Example custom runtime that demonstrates the RuntimeAdapter contract.

    To integrate a real model backend, replace the stub logic in respond()
    with actual API calls.
    """

    def __init__(self, api_key: str = "", model: str = "my-model"):
        self.api_key = api_key
        self.model = model

    def respond(self, context: dict) -> RuntimeResponse:
        """
        Send context to your model backend and return a RuntimeResponse.

        Args:
            context: Dict containing user_request, project, plan, tool_results, etc.

        Returns:
            RuntimeResponse with content, tool_calls, and finish_reason.
        """
        user_request = context.get("user_request", "")

        # Stub: replace with actual API call
        if "tool" in user_request.lower():
            return RuntimeResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        tool="read_file",
                        arguments={"path": "example.py"},
                    )
                ],
                finish_reason=FinishReason.TOOL_CALLS,
            )

        return RuntimeResponse(
            content=f"Custom runtime processed: {user_request}",
            finish_reason=FinishReason.STOP,
        )

    def capabilities(self) -> dict:
        """Declare what this runtime supports."""
        return {
            "text_generation": True,
            "tool_calls": True,
            "external_tool_execution": True,
            "streaming": False,
            "cancellation": False,
        }

    def cancel(self) -> None:
        """Cancel an in-flight request if supported."""
        pass

    @property
    def default_model(self) -> str | None:
        return self.model


def register_runtime():
    """Register this runtime with AgentCore's runtime registry."""
    from agentcore.runtimes import get_default_registry

    registry = get_default_registry()
    registry.register(
        "my-custom",
        lambda **kwargs: MyCustomRuntime(**kwargs),
        info={
            "description": "My custom model backend",
            "capabilities": {
                "text_generation": True,
                "tool_calls": True,
                "external_tool_execution": True,
                "streaming": False,
                "cancellation": False,
            },
        },
    )
    print("Registered custom runtime: my-custom")


if __name__ == "__main__":
    register_runtime()
    print("Custom runtime example loaded.")
