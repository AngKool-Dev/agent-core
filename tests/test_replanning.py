"""
Tests for replanning, tool failure handling, and cancellation (Phase 6).

Covers:
- Tool failure recovery via replanning
- Verification failure recovery via replanning
- max_replans enforcement
- Cancellation mid-iteration and mid-tool
- Runtime cancellation contract
"""

from unittest.mock import MagicMock, patch

from agentcore import Agent, AgentConfig, TaskState
from agentcore.events import EventBus, EventType
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.runtimes.base import (
    FinishReason,
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
)


class InMemoryBackendForReplan(MemoryBackend):
    def __init__(self):
        self._store = []

    def search(self, query, project=None, limit=20):
        return []

    def store(self, type, content, project=None, importance=0.5):
        mem = {
            "id": f"mem-{len(self._store)}",
            "type": type,
            "content": content,
            "project": project,
        }
        self._store.append(mem)
        return mem

    def update(self, memory_id, content):
        return {}

    def list(self, project=None, type=None, limit=50):
        return self._store


class RecorderRuntime(RuntimeAdapter):
    def __init__(self, responses):
        self._responses = list(responses)
        self._index = 0
        self.cancelled = False
        self.calls = []

    def respond(self, context):
        self.calls.append(context)
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

    def capabilities(self):
        return {
            "adapter": "recorder",
            "text_generation": True,
            "tool_calls": True,
            "external_tool_execution": True,
            "streaming": False,
            "cancellation": False,
        }

    def cancel(self):
        self.cancelled = True


class TestToolFailureReplanning:
    def test_tool_failure_triggers_replanning_state(self, tmp_path):
        responses = [
            RuntimeResponse(
                content="I'll run a tool",
                tool_calls=[ToolCall(tool="unknown_tool", arguments={})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Replanned and fixed", finish_reason=FinishReason.STOP),
        ]
        runtime = RecorderRuntime(responses)
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
            max_replans=2,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Test tool failure replanning", str(tmp_path))
        assert result["success"] is True
        assert agent._replan_count >= 1

    def test_tool_failure_respects_max_replans(self, tmp_path):
        responses = [
            RuntimeResponse(
                content="I'll run a tool",
                tool_calls=[ToolCall(tool="unknown_tool", arguments={})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(
                content="Try again",
                tool_calls=[ToolCall(tool="unknown_tool", arguments={})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(
                content="Try again",
                tool_calls=[ToolCall(tool="unknown_tool", arguments={})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Done", finish_reason=FinishReason.STOP),
        ]
        runtime = RecorderRuntime(responses)
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=20,
            enable_verification=False,
            max_replans=1,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        agent.execute("Test max replans", str(tmp_path))
        assert agent._replan_count <= 1

    def test_successful_tool_does_not_replan(self, tmp_path):
        (tmp_path / "source.txt").write_text("hello")
        responses = [
            RuntimeResponse(
                content="I'll read the file",
                tool_calls=[ToolCall(tool="read_file", arguments={"path": "source.txt"})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Done", finish_reason=FinishReason.STOP),
        ]
        runtime = RecorderRuntime(responses)
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
            max_replans=2,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Test no replan on success", str(tmp_path))
        assert agent._replan_count == 0
        assert result["success"] is True


class TestVerificationFailureReplanning:
    def test_verification_failure_triggers_replanning(self, tmp_path):
        responses = [
            RuntimeResponse(content="Initial work", finish_reason=FinishReason.STOP),
            RuntimeResponse(
                content="Fixed after verification failure", finish_reason=FinishReason.STOP
            ),
        ]
        runtime = RecorderRuntime(responses)
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=True,
            run_format_check=True,
            run_build_check=True,
            run_tests=True,
            max_replans=2,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        with patch.object(agent._verifier, "verify_all") as mock_verify:
            mock_verify.return_value = MagicMock(
                to_dict=MagicMock(
                    return_value={
                        "overall_passed": False,
                        "failures": ["tests failed"],
                    }
                )
            )
            agent.execute("Test verification replanning", str(tmp_path))
        assert agent._replan_count >= 1

    def test_verification_success_completes(self, tmp_path):
        responses = [
            RuntimeResponse(content="Work done", finish_reason=FinishReason.STOP),
        ]
        runtime = RecorderRuntime(responses)
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=True,
            run_format_check=True,
            run_build_check=True,
            run_tests=True,
            max_replans=2,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        with patch.object(agent._verifier, "verify_all") as mock_verify:
            mock_verify.return_value = MagicMock(
                to_dict=MagicMock(
                    return_value={
                        "overall_passed": True,
                        "failures": [],
                    }
                )
            )
            result = agent.execute("Test verification success", str(tmp_path))
        assert agent._replan_count == 0
        assert result["success"] is True


class TestCancellation:
    def test_cancel_sets_cancelled_state(self, tmp_path):
        runtime = RecorderRuntime(
            [RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)]
        )
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        agent.execute("Test cancel", str(tmp_path))
        assert agent._cancelled is False
        agent.cancel()
        assert agent._cancelled is True
        assert agent._current_task.current_state == TaskState.CANCELLED

    def test_cancel_calls_runtime_cancel(self, tmp_path):
        runtime = RecorderRuntime(
            [RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)]
        )
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        agent.execute("Test cancel runtime", str(tmp_path))
        agent.cancel()
        assert runtime.cancelled is True

    def test_cancel_before_execute_is_noop(self, tmp_path):
        runtime = RecorderRuntime(
            [RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)]
        )
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        agent.cancel()
        result = agent.execute("Test cancel before execute", str(tmp_path))
        assert "task" in result

    def test_cancel_during_execution(self, tmp_path):
        call_count = [0]

        class SlowRuntime(RuntimeAdapter):
            def respond(self, context):
                call_count[0] += 1
                if call_count[0] == 1:
                    return RuntimeResponse(
                        content="I'll run a tool",
                        tool_calls=[
                            ToolCall(tool="run_command", arguments={"command": "sleep 10"})
                        ],
                        finish_reason=FinishReason.TOOL_CALLS,
                    )
                return RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)

            def capabilities(self):
                return {
                    "adapter": "slow",
                    "text_generation": True,
                    "tool_calls": True,
                    "external_tool_execution": True,
                    "streaming": False,
                    "cancellation": False,
                }

            def cancel(self):
                pass

        runtime = SlowRuntime()
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)

        import threading

        def run():
            agent.execute("Test cancel during execution", str(tmp_path))

        thread = threading.Thread(target=run)
        thread.start()
        import time

        time.sleep(0.1)
        agent.cancel()
        thread.join(timeout=5)
        assert agent._cancelled is True


class TestRecoverableVsTerminalFailures:
    def test_recoverable_tool_failure_leads_to_replanning(self, tmp_path):
        responses = [
            RuntimeResponse(
                content="I'll run a tool",
                tool_calls=[ToolCall(tool="unknown_tool", arguments={})],
                finish_reason=FinishReason.TOOL_CALLS,
            ),
            RuntimeResponse(content="Recovered", finish_reason=FinishReason.STOP),
        ]
        runtime = RecorderRuntime(responses)
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=5,
            max_tool_calls=10,
            enable_verification=False,
            max_replans=2,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        result = agent.execute("Test recoverable", str(tmp_path))
        assert result["success"] is True

    def test_terminal_cancellation_sets_failed_or_cancelled(self, tmp_path):
        runtime = RecorderRuntime(
            [RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)]
        )
        memory = MemoryManager(InMemoryBackendForReplan())
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(runtime=runtime, memory=memory, config=config, project_path=tmp_path)
        agent.execute("Test terminal", str(tmp_path))
        agent.cancel()
        assert agent._current_task.current_state in (TaskState.CANCELLED, TaskState.FAILED)


class TestStateEvents:
    def test_state_change_event_emitted(self, tmp_path):
        runtime = RecorderRuntime(
            [RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)]
        )
        memory = MemoryManager(InMemoryBackendForReplan())
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e))
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path, event_bus=bus
        )
        agent.execute("Test state events", str(tmp_path))
        state_events = [e for e in received if e.event_type == EventType.TASK_STATE_CHANGED]
        assert len(state_events) > 0
        for event in state_events:
            assert "previous_state" in event.data
            assert "new_state" in event.data

    def test_task_cancelled_event_emitted(self, tmp_path):
        runtime = RecorderRuntime(
            [RuntimeResponse(content="Done", finish_reason=FinishReason.STOP)]
        )
        memory = MemoryManager(InMemoryBackendForReplan())
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e))
        config = AgentConfig(
            max_iterations=10,
            max_tool_calls=10,
            enable_verification=False,
        )
        agent = Agent(
            runtime=runtime, memory=memory, config=config, project_path=tmp_path, event_bus=bus
        )
        agent.execute("Test cancel event", str(tmp_path))
        agent.cancel()
        cancel_events = [e for e in received if e.event_type == EventType.TASK_CANCELLED]
        assert len(cancel_events) == 1
        assert cancel_events[0].data["task_id"] == agent._current_task.task_id
