"""
Multi-runtime integration test for AgentCore.

Proves the pluggable architecture: AgentCore can route work through a
runtime adapter other than Hermes, collect observations, and harvest
memories — without any changes to AgentCore core logic.

This is the production-grade validation that the "runtime-agnostic"
claim is real, not just architectural.
"""

from pathlib import Path

from agentcore import (
    Agent,
    AgentConfig,
    EchoRuntime,
    EventBus,
    EventType,
    InMemoryBackend,
    MemoryManager,
)
from agentcore.runtimes import get_default_registry


def _make_project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")


class TestMultiRuntimeArchitecture:
    """Prove AgentCore works with multiple independent runtimes."""

    def test_both_hermes_and_echo_registered(self):
        """EchoRuntime is registered alongside Hermes in the default registry."""
        reg = get_default_registry()
        runtimes = reg.list_runtimes()
        assert "hermes" in runtimes
        assert "echo" in runtimes

    def test_echo_runtime_is_tool_aware(self):
        """EchoRuntime declares tool_calls + external_tool_execution (unlike Hermes)."""
        reg = get_default_registry()
        echo_caps = reg.get_capabilities("echo")
        hermes_caps = reg.get_capabilities("hermes")

        assert echo_caps["tool_calls"] is True
        assert echo_caps["external_tool_execution"] is True
        assert hermes_caps["tool_calls"] is False
        assert hermes_caps["external_tool_execution"] is False

    def test_echo_runtime_conforms_to_adapter(self):
        """EchoRuntime is a proper RuntimeAdapter subclass."""
        from agentcore.runtimes.base import RuntimeAdapter

        runtime = EchoRuntime()
        assert isinstance(runtime, RuntimeAdapter)

    def test_echo_runtime_capabilities_match_declared(self):
        """Capabilities from the registry match what EchoRuntime reports."""
        reg = get_default_registry()
        registry_caps = reg.get_capabilities("echo")

        runtime = EchoRuntime()
        direct_caps = runtime.capabilities()

        assert direct_caps["adapter"] == "echo"
        assert direct_caps["text_generation"] == registry_caps["text_generation"]
        assert direct_caps["tool_calls"] == registry_caps["tool_calls"]

    def test_task_routes_through_echo_runtime(self, tmp_path):
        """An AgentCore task can be completed through EchoRuntime, not Hermes."""
        _make_project(tmp_path)
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))

        runtime = EchoRuntime()
        memory = MemoryManager(InMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(
                max_iterations=5,
                max_tool_calls=10,
                enable_verification=False,
            ),
            project_path=tmp_path,
            event_bus=bus,
        )

        result = agent.execute("Echo this request", str(tmp_path))

        assert result["success"] is True
        assert result["task"]["current_state"] == "COMPLETED"
        assert runtime.call_count >= 1

        event_types = [e.event_type for e in events]
        assert EventType.TASK_STARTED in event_types
        assert EventType.TASK_COMPLETED in event_types

    def test_observations_collected_from_echo_runtime(self, tmp_path):
        """AgentCore collects observations from a non-Hermes runtime."""
        _make_project(tmp_path)
        bus = EventBus()
        observations = []
        bus.subscribe(lambda e: observations.append(e))

        runtime = EchoRuntime()
        memory = MemoryManager(InMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(
                max_iterations=5,
                max_tool_calls=10,
                enable_verification=False,
            ),
            project_path=tmp_path,
            event_bus=bus,
        )

        agent.execute("Echo this", str(tmp_path))

        assert len(observations) >= 1

    def test_memory_harvested_from_echo_runtime(self, tmp_path):
        """Memory harvesting works with a non-Hermes runtime."""
        _make_project(tmp_path)
        runtime = EchoRuntime()
        backend = InMemoryBackend()
        memory = MemoryManager(backend)

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=AgentConfig(
                max_iterations=5,
                max_tool_calls=10,
                enable_verification=False,
            ),
            project_path=tmp_path,
        )

        result = agent.execute("Echo this request", str(tmp_path))

        assert result["success"] is True
        assert len(backend.list()) >= 1

    def test_echo_vs_hermes_have_different_capabilities(self):
        """The two runtimes are genuinely different (not aliases)."""
        from agentcore.runtimes.base import RuntimeAdapter

        echo = EchoRuntime()
        hermes = get_default_registry().create("hermes")

        assert isinstance(echo, RuntimeAdapter)
        assert isinstance(hermes, RuntimeAdapter)
        assert echo.capabilities() != hermes.capabilities()

    def test_echo_runtime_via_registry(self):
        """EchoRuntime can be instantiated via the registry factory pattern."""
        reg = get_default_registry()
        runtime = reg.create("echo")
        assert isinstance(runtime, EchoRuntime)

        response = runtime.respond({"user_request": "hello world"})
        assert response.finish_reason.value == "stop"
        assert "hello world" in response.content
