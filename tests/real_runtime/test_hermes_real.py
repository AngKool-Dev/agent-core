"""
Real runtime integration tests.

These tests require actual runtime binaries to be installed and available
in PATH. They are explicitly opt-in via:

    AGENTCORE_REAL_RUNTIME=1 pytest -m real_runtime -q

"""

import os
import shutil

import pytest

from agentcore import Agent, AgentConfig, create_agent
from agentcore.memory import MemoryManager
from agentcore.runtimes.hermes import HermesRuntime
from agentcore.runtimes.base import RuntimeResponse, FinishReason


pytestmark = pytest.mark.real_runtime


def _require_hermes() -> str:
    """Return the path to the hermes binary, or skip if not available."""
    path = shutil.which("hermes")
    if not path:
        pytest.skip("hermes binary not found in PATH")
    return path


class TestHermesRealRuntime:
    """Tests that exercise the real Hermes CLI subprocess."""

    def test_hermes_binary_detected(self):
        """The hermes binary must be discoverable in PATH."""
        path = _require_hermes()
        assert os.path.isfile(path)

    def test_hermes_runtime_responds_to_simple_prompt(self):
        """HermesRuntime should return a RuntimeResponse for a simple prompt."""
        _require_hermes()
        runtime = HermesRuntime(timeout=60)
        context = {
            "prompt": "Reply with exactly: AGENTCORE_E2E_TEST",
            "user_request": "Reply with exactly: AGENTCORE_E2E_TEST",
            "project": ".",
            "selected_skills": [],
            "plan": [],
            "tool_results": [],
            "observations": [],
        }
        response = runtime.respond(context)

        assert isinstance(response, RuntimeResponse)
        assert response.finish_reason != FinishReason.ERROR

    def test_hermes_agent_end_to_end(self, tmp_path):
        """Agent should complete a text task through the real Hermes CLI."""
        _require_hermes()
        runtime = HermesRuntime(timeout=120)
        memory = MemoryManager(InMemoryBackend())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
        )

        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Reply with exactly: AGENTCORE_E2E_TEST")

        assert result["success"] is True
        assert result["task"]["current_state"] == "COMPLETED"
        assert result["tools_used"] == 0


class InMemoryBackend:
    """Simple in-memory memory backend for tests."""

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
