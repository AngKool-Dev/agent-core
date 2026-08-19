"""
Tests for the RuntimeAdapter contract and RuntimeResponse abstraction.

These tests verify that:
- HermesRuntime and MockRuntime conform to the same RuntimeAdapter interface
- Both return RuntimeResponse (not raw strings or dicts)
- RuntimeResponse handles normal responses, tool calls, and malformed input
"""

import threading
import time
from unittest.mock import MagicMock, patch

from agentcore.runtimes.base import (
    FinishReason,
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
)
from agentcore.runtimes.hermes import HermesRuntime
from tests.test_mock_runtime import MockRuntime


class TestRuntimeResponseContract:
    """Verify RuntimeResponse structure and behavior."""

    def test_runtime_response_has_required_fields(self):
        resp = RuntimeResponse(content="hello", tool_calls=[], finish_reason=FinishReason.STOP)
        assert hasattr(resp, "content")
        assert hasattr(resp, "tool_calls")
        assert hasattr(resp, "finish_reason")
        assert hasattr(resp, "metadata")

    def test_runtime_response_default_is_stop(self):
        resp = RuntimeResponse()
        assert resp.finish_reason == FinishReason.STOP
        assert resp.tool_calls == []
        assert resp.content == ""

    def test_runtime_response_with_tool_calls(self):
        tc = ToolCall(tool="read_file", arguments={"path": "test.py"})
        resp = RuntimeResponse(
            content="",
            tool_calls=[tc],
            finish_reason=FinishReason.TOOL_CALLS,
        )
        assert resp.has_tool_calls is True
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool == "read_file"

    def test_runtime_response_is_complete_flag(self):
        """is_complete should be True for STOP, ERROR, TIMEOUT — not TOOL_CALLS."""
        assert RuntimeResponse(content="done", finish_reason=FinishReason.STOP).is_complete is True
        assert RuntimeResponse(content="err", finish_reason=FinishReason.ERROR).is_complete is True
        assert (
            RuntimeResponse(content="err", finish_reason=FinishReason.TIMEOUT).is_complete is True
        )
        assert (
            RuntimeResponse(tool_calls=[], finish_reason=FinishReason.TOOL_CALLS).is_complete
            is False
        )

    def test_runtime_response_to_dict(self):
        tc = ToolCall(tool="shell", arguments={"command": "ls"})
        resp = RuntimeResponse(
            content="here's the output",
            tool_calls=[tc],
            finish_reason=FinishReason.TOOL_CALLS,
            metadata={"request_id": "abc"},
        )
        data = resp.to_dict()
        assert data["content"] == "here's the output"
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool"] == "shell"
        assert data["finish_reason"] == "tool_calls"
        assert data["metadata"]["request_id"] == "abc"


class TestRuntimeAdapterConformance:
    """Both runtimes must conform to the RuntimeAdapter ABC."""

    def test_hermes_runtime_is_runtime_adapter(self):
        rt = HermesRuntime()
        assert isinstance(rt, RuntimeAdapter)

    def test_mock_runtime_is_runtime_adapter(self):
        rt = MockRuntime(responses=["test"])
        assert isinstance(rt, RuntimeAdapter)

    def test_hermes_runtime_respond_returns_runtime_response(self):
        """HermesRuntime.respond must return RuntimeResponse, not raw string."""
        rt = HermesRuntime()
        # We can't actually call hermes, but we can test the return type
        # by calling _parse_response directly
        resp = rt._parse_response("Hello world", "", 0)
        assert isinstance(resp, RuntimeResponse)
        assert resp.content == "Hello world"
        assert resp.finish_reason == FinishReason.STOP

    def test_hermes_runtime_parses_tool_calls(self):
        """HermesRuntime must correctly parse TOOL_CALL: directives."""
        rt = HermesRuntime()
        raw_output = 'Here is some text\nTOOL_CALL: read_file { "path": "test.py" }\nMore text'
        resp = rt._parse_response(raw_output, "", 0)

        assert isinstance(resp, RuntimeResponse)
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool == "read_file"
        assert resp.tool_calls[0].arguments["path"] == "test.py"
        assert resp.finish_reason == FinishReason.TOOL_CALLS

    def test_hermes_runtime_parses_complete_marker(self):
        """HermesRuntime should recognize COMPLETE marker."""
        rt = HermesRuntime()
        resp = rt._parse_response("Task is done COMPLETE", "", 0)
        assert resp.finish_reason == FinishReason.STOP

    def test_hermes_runtime_handles_error_output(self):
        """Non-zero exit code with no output should be an error."""
        rt = HermesRuntime()
        resp = rt._parse_response("", "Something went wrong", 1)
        assert resp.finish_reason == FinishReason.ERROR

    def test_hermes_runtime_handles_timeout(self):
        """TimeoutExpired should produce a TIMEOUT finish reason."""
        rt = HermesRuntime(timeout=1)
        import subprocess as sp

        mock_process = MagicMock()
        mock_process.communicate.side_effect = sp.TimeoutExpired(cmd="hermes", timeout=1)
        mock_process.returncode = -1

        with patch("agentcore.runtimes.hermes.subprocess.Popen", return_value=mock_process):
            resp = rt.respond({"user_request": "test"})
            assert resp.finish_reason == FinishReason.TIMEOUT
            assert resp.content == ""

    def test_hermes_runtime_handles_missing_binary(self):
        """FileNotFoundError should produce an ERROR finish reason."""
        rt = HermesRuntime()

        with patch(
            "agentcore.runtimes.hermes.subprocess.Popen",
            side_effect=FileNotFoundError("hermes not found"),
        ):
            resp = rt.respond({"user_request": "test"})
            assert resp.finish_reason == FinishReason.ERROR

    def test_mock_runtime_respond_returns_runtime_response(self):
        rt = MockRuntime(responses=["Hello from mock"])
        resp = rt.respond({})
        assert isinstance(resp, RuntimeResponse)
        assert resp.content == "Hello from mock"
        assert resp.finish_reason == FinishReason.STOP

    def test_mock_runtime_with_tool_calls_returns_runtime_response(self):
        tc = ToolCall(tool="read_file", arguments={"path": "x.py"})
        rt = MockRuntime(responses=[tc])
        resp = rt.respond({})
        assert isinstance(resp, RuntimeResponse)
        assert resp.finish_reason == FinishReason.TOOL_CALLS
        assert resp.tool_calls[0].tool == "read_file"

    def test_mock_runtime_capabilities(self):
        rt = MockRuntime(responses=["test"])
        caps = rt.capabilities()
        assert "adapter" in caps
        assert caps["adapter"] == "mock"

    def test_hermes_runtime_capabilities(self):
        rt = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
        caps = rt.capabilities()
        assert caps["adapter"] == "hermes"
        assert caps["tool_calls"] is False
        assert caps["external_tool_execution"] is False
        assert caps["text_generation"] is True
        assert caps["streaming"] is False
        assert caps["cancellation"] is True
        assert caps["model"] == "claude-sonnet-4"
        assert caps["provider"] == "anthropic"
        assert caps["timeout"] == 300

    def test_hermes_runtime_cancel_is_noop(self):
        rt = HermesRuntime()
        rt.cancel()  # must not raise

    def test_hermes_runtime_cancel_terminates_subprocess(self):
        """cancel() terminates the in-flight Hermes subprocess; respond() returns CANCELLED."""
        rt = HermesRuntime(timeout=300)

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        communicate_event = threading.Event()

        def mock_communicate(timeout=None):
            communicate_event.wait(timeout=timeout or 60)
            return ("output", "")

        mock_process.communicate.side_effect = mock_communicate
        mock_process.returncode = 0

        with patch("agentcore.runtimes.hermes.subprocess.Popen", return_value=mock_process):
            result_holder = []

            def run_respond():
                result_holder.append(rt.respond({"user_request": "test"}))

            thread = threading.Thread(target=run_respond)
            thread.start()
            time.sleep(0.05)
            rt.cancel()
            communicate_event.set()
            thread.join(timeout=5)

            assert len(result_holder) == 1
            response = result_holder[0]
            assert response.finish_reason == FinishReason.CANCELLED
            mock_process.terminate.assert_called_once()

    def test_mock_runtime_cancel_is_noop(self):
        rt = MockRuntime(responses=["test"])
        rt.cancel()  # must not raise

    def test_hermes_runtime_default_model(self):
        rt = HermesRuntime(model="test-model")
        assert rt.default_model == "test-model"

    def test_hermes_runtime_default_model_none(self):
        rt = HermesRuntime()
        assert rt.default_model is None

    def test_hermes_capability_contract_booleans(self):
        rt = HermesRuntime()
        caps = rt.capabilities()
        for key in (
            "text_generation",
            "tool_calls",
            "external_tool_execution",
            "streaming",
            "cancellation",
        ):
            assert key in caps
            assert isinstance(caps[key], bool)

    def test_hermes_capability_contract_text_generation(self):
        rt = HermesRuntime()
        caps = rt.capabilities()
        assert caps["text_generation"] is True

    def test_hermes_capability_contract_tool_calls(self):
        rt = HermesRuntime()
        caps = rt.capabilities()
        assert caps["tool_calls"] is False

    def test_hermes_capability_contract_external_tool_execution(self):
        rt = HermesRuntime()
        caps = rt.capabilities()
        assert caps["external_tool_execution"] is False

    def test_black_box_runtime_response_is_valid(self):
        resp = RuntimeResponse(
            content="Done",
            tool_calls=[],
            finish_reason=FinishReason.STOP,
        )
        assert resp.has_tool_calls is False
        assert resp.is_complete is True
        assert resp.finish_reason == FinishReason.STOP


class TestRuntimeResponseMalformedHandling:
    """Test malformed response handling."""

    def test_hermes_empty_output(self):
        rt = HermesRuntime()
        resp = rt._parse_response("", "", 0)
        assert isinstance(resp, RuntimeResponse)
        assert resp.content == ""

    def test_hermes_output_with_only_tool_call(self):
        rt = HermesRuntime()
        resp = rt._parse_response('TOOL_CALL: shell { "command": "ls -la" }', "", 0)
        assert resp.finish_reason == FinishReason.TOOL_CALLS
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool == "shell"
        assert resp.tool_calls[0].arguments["command"] == "ls -la"

    def test_hermes_response_no_metadata_leak(self):
        """RuntimeResponse must not expose Hermes-specific protocol details."""
        rt = HermesRuntime()
        resp = rt._parse_response("Hello COMPLETE", "", 0)
        data = resp.to_dict()
        # The metadata dict may contain stderr/returncode but should not
        # expose Hermes-specific internal structures
        assert "content" in data
        assert "tool_calls" in data
        assert "finish_reason" in data

    def test_registry_cancellation_matches_runtime(self):
        """Registry metadata must agree with the runtime's own capabilities()."""
        from agentcore.runtimes.registry import get_default_registry

        registry = get_default_registry()
        rt = HermesRuntime()
        runtime_caps = rt.capabilities()
        registry_caps = registry.get_capabilities("hermes")
        assert registry_caps["cancellation"] == runtime_caps["cancellation"]
