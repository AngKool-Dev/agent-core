"""
Basic AgentCore usage example.

Run: python examples/basic_agent.py
"""

from agentcore import Agent, AgentConfig
from agentcore.memory import InMemoryBackend, MemoryManager
from agentcore.runtimes.base import FinishReason, RuntimeAdapter, RuntimeResponse


class EchoRuntime(RuntimeAdapter):
    """Simple runtime that echoes the prompt back."""

    def respond(self, context):
        user_request = context.get("user_request", "")
        return RuntimeResponse(
            content=f"Echo: {user_request}",
            finish_reason=FinishReason.STOP,
        )

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
        return "echo"


def main():
    runtime = EchoRuntime()
    memory = MemoryManager(InMemoryBackend())
    config = AgentConfig(
        max_iterations=5,
        max_tool_calls=10,
        enable_verification=False,
    )

    agent = Agent(runtime=runtime, memory=memory, config=config)
    result = agent.execute("Hello, AgentCore!")

    print(f"Task: {result['task']['task_id']}")
    print(f"State: {result['task']['current_state']}")
    print(f"Success: {result['success']}")


if __name__ == "__main__":
    main()
